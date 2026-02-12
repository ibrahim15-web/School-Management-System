from django.shortcuts import render
from accounts.models import CustomUser
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import transaction
import logging
from django.contrib import messages
from django.core.mail import send_mass_mail
import json
import uuid

# Create your views here.

def home(request):
    total_students = CustomUser.objects.filter(is_student=True, is_member_of_this_school=True).count()
    total_teachers = CustomUser.objects.filter(is_teacher=True, is_member_of_this_school=True).count()

    context = {
        "total_students": total_students,
        "total_teachers": total_teachers,
    }
    return render(request, 'pages/home.html', context)

@login_required(login_url='login')
def admin_dashboard(request):
    # allow only staff or superuser accounts
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'You do not have permission to access the admin dashboard.')
        return render(request, 'pages/home.html', {})

    # Fetching Data
    pending_users_queryset = CustomUser.objects.filter(
    is_member_of_this_school=False).exclude(status='rejected').order_by('-date_joined')

    # Prepare data for JS (Search/Sort functionality)
    # We convert the queryset to a list of dictionaries
    pending_users_list = list(pending_users_queryset.values(
    'id',
    'username',
    'email',
    'phone_number',
    'date_joined',
    'first_name',
    'last_name',
    'is_student',
    'is_teacher',))
    # Convert UUIDs and Dates to strings for JSON compatibility
    for user in pending_users_list:
        user['id'] = str(user['id'])
        user['date_joined'] = user['date_joined'].strftime('%Y-%m-%dT%H:%M:%S')
        user['full_name'] = f"{user['first_name']} {user['last_name']}".strip() or user['username']
        if user['is_student']:
            user['role'] = 'student'
        elif user['is_teacher']:
            user['role'] = 'teacher'
        else:
            user['role'] = 'student'  # safe default
    context = {
        "pending_count": pending_users_queryset.count(),
        "pending_students": pending_users_queryset.filter(is_student=True).count(),
        "pending_teachers": pending_users_queryset.filter(is_teacher=True).count(),
        "total_students": CustomUser.objects.filter(is_student=True, is_member_of_this_school=True).count(),
        "total_teachers": CustomUser.objects.filter(is_teacher=True, is_member_of_this_school=True).count(),
        "pending_users_json": pending_users_list, # For JS
    }
    return render(request, 'pages/admin_dashboard.html', context)

logger = logging.getLogger(__name__)
@login_required
def process_pending_registrations(request):
    """
    Single API endpoint to approve or reject pending user registrations.
    Handles both single and bulk actions.
   
    Expected JSON payload:
    {
        "action": "approve" | "reject",
        "users": [
            {
                "id": "uuid-string",
                "role": "student" | "teacher" | "parent" | "admin" | null
            }
        ],
        "reason": "string (required for reject, null/omitted for approve)"
    }
    
    Note: processed_count excludes skipped users (already processed, missing, etc.)
    """
    
    # 1. Method check (validate request type first)
    if request.method != 'POST':
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid request method'
        }, status=405)
    
    # 2. Authorization check
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({
            'status': 'error',
            'message': 'Unauthorized access'
        }, status=403)
    
    # 3. Parse JSON body
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON format'
        }, status=400)
    
    # 4. Extract and validate required fields
    action = data.get('action')
    users_data = data.get('users', [])
    reason = (data.get('reason') or '').strip()
    # Normalize single user → list
    if isinstance(users_data, dict):
        users_data = [users_data]
    # Validate action
    if action not in ['approve', 'reject']:
        return JsonResponse({
            'status': 'error',
            'message': f'Invalid action: {action}'
        }, status=400)
    
    # Validate users list
    if not users_data or not isinstance(users_data, list):
        return JsonResponse({
            'status': 'error',
            'message': 'No users provided'
        }, status=400)
    
    # 5. Action-specific validation
    if action == 'reject':
        # Rejection reason is MANDATORY
        if not reason:
            return JsonResponse({
                'status': 'error',
                'message': 'Rejection reason is required'
            }, status=400)
    
    if action == 'approve':
        # All users must have a role
        for user_item in users_data:
            if not user_item.get('role'):
                return JsonResponse({
                    'status': 'error',
                    'message': 'Role is required for all users during approval'
                }, status=400)
    
    # 6. Define role mapping once (outside loop)
    # UPDATED: Clean separation between business role and Django permission
    ROLE_MAP = {
        'student': 'is_student',
        'teacher': 'is_teacher',
        'parent': 'is_parent',
        'admin': 'is_admin',   # ✅ NOW USES BUSINESS ROLE, NOT is_staff
    }
    
    # 7. Process users in a transaction
    email_messages = []
    processed_count = 0  # Only counts successfully processed users (not skipped)
    
    try:
        with transaction.atomic():
            for item in users_data:
                try:
                    # Convert string UUID to UUID object for safety
                    user_id = uuid.UUID(item['id'])
                    user = CustomUser.objects.get(id=user_id)
                    
                    # Prevent re-processing already-handled users
                    if action == 'approve' and user.status == 'approved':
                        logger.info(f"User {user.username} already approved, skipping")
                        continue
                    
                    if action == 'reject' and user.status == 'rejected':
                        logger.info(f"User {user.username} already rejected, skipping")
                        continue
                    
                    if action == 'approve':
                        role = item['role']
                        
                        # Validate role
                        if role not in ROLE_MAP:
                            raise ValueError(f"Invalid role: {role}")
                        
                        # Reset all role flags (ensures one role only)
                        user.is_student = False
                        user.is_teacher = False
                        user.is_parent = False
                        user.is_admin = False 
                        user.is_staff = False
                        
                        # Set the selected role
                        setattr(user, ROLE_MAP[role], True)
                        
                        # Activate the user
                        user.is_member_of_this_school = True
                        user.is_active = True
                        user.status = 'approved'
                        user.rejection_reason = None  # Clear any previous rejection
                        user.save()
                        
                        # Queue approval email
                        if user.email:
                            email_messages.append((
                                "Your account has been approved",
                                f"Hi {user.username},\n\n"
                                f"Your account has been approved as a {role}.\n"
                                f"You can now log in to the system.\n\n"
                                f"Best regards,\n"
                                f"School Administration",
                                settings.EMAIL_HOST_USER,
                                [user.email]
                            ))
                        
                        processed_count += 1
                    
                    elif action == 'reject':
                        # Clear all roles
                        user.is_student = False
                        user.is_teacher = False
                        user.is_parent = False
                        user.is_admin = False
                        user.is_staff = False
                        
                        # Deactivate and mark as rejected
                        user.is_active = False
                        user.is_member_of_this_school = False
                        user.status = 'rejected'
                        user.rejection_reason = reason
                        user.save()
                        
                        # Queue rejection email
                        if user.email:
                            email_messages.append((
                                "Registration Request Update",
                                f"Hi {user.username},\n\n"
                                f"Your registration request has been rejected.\n\n"
                                f"Reason: {reason}\n\n"
                                f"If you have questions, please contact the school administration.\n\n"
                                f"Best regards,\n"
                                f"School Administration",
                                settings.EMAIL_HOST_USER,
                                [user.email]
                            ))
                        
                        processed_count += 1
                
                except CustomUser.DoesNotExist:
                    logger.warning(f"User {item['id']} not found, skipping")
                    # Don't fail the whole transaction for missing users
                    # Just skip and continue
                    continue
                
                except ValueError as ve:
                    logger.error(f"Validation error: {ve}")
                    raise  # Re-raise to trigger transaction rollback
        
        # 8. Send emails (outside transaction to avoid rollback on email failure)
        if email_messages:
            try:
                send_mass_mail(email_messages, fail_silently=False)
            except Exception as e:
                logger.error(f"Email sending failed: {e}")
                # Users were still processed successfully
                return JsonResponse({
                    'status': 'partial_success',
                    'message': f'{processed_count} user(s) processed, but emails failed to send',
                    'count': processed_count
                })
        
        # 9. Success response
        return JsonResponse({
            'status': 'success',
            'count': processed_count
        })
    
    except ValueError as ve:
        # Validation errors (invalid role, etc.)
        return JsonResponse({
            'status': 'error',
            'message': str(ve)
        }, status=400)
    
    except Exception as e:
        # Unexpected errors
        logger.error(f"Unexpected error in process_pending_registrations: {e}")
        return JsonResponse({
            'status': 'error',
            'message': 'An unexpected error occurred'
        }, status=500)