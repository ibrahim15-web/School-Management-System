import json
import uuid
import logging
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Q
from django.core.mail import send_mass_mail
from datetime import timedelta
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.contrib import messages
# Local import
from accounts.models import CustomUser
from academics.models import AcademicYear, Class
from core.models import Announcement, Notification
from teachers.models import Attendance
from teachers.analytics import get_last_7_days_attendance, get_today_attendance_summary, get_last_7_days_teacher_attendance, get_today_teacher_attendance_summary


def home(request):
    total_students = CustomUser.objects.filter(is_student=True, is_member_of_this_school=True).count()
    total_teachers = CustomUser.objects.filter(is_teacher=True, is_member_of_this_school=True).count()
    try:
        current_year = AcademicYear.objects.get(is_current=True)
    except AcademicYear.DoesNotExist:
        current_year = None
    total_classes = 0
    if current_year:
        total_classes = Class.objects.filter(
            academic_year=current_year
        ).count()
    today_summary = get_today_attendance_summary()
    announcements = _get_announcements_for_user(request.user, limit=5)
    context = {
        'total_students':   total_students,
        'total_teachers':   total_teachers,
        'total_classes':    total_classes,
        'current_year':     current_year,
        'today_percentage': today_summary['percentage'],
        'today_total':      today_summary['total'],
        'announcements':    announcements,
    }
    return render(request, 'pages/home.html', context)

@login_required(login_url='login')
def admin_dashboard(request):
    # allow only staff or superuser accounts
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'You do not have permission to access the admin dashboard.')
        return render(request, 'pages/home.html', {})

    # --- Pending users ---
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
    
    # --- Analytics ---

    student_chart   = get_last_7_days_attendance()
    teacher_chart   = get_last_7_days_teacher_attendance()
    student_today   = get_today_attendance_summary()
    teacher_today   = get_today_teacher_attendance_summary()

    context = { 
        # Pending registrations
        "pending_count": pending_users_queryset.count(),
        "pending_students": pending_users_queryset.filter(is_student=True).count(),
        "pending_teachers": pending_users_queryset.filter(is_teacher=True).count(),
        # School totals
        "total_students": CustomUser.objects.filter(is_student=True, is_member_of_this_school=True).count(),
        "total_teachers": CustomUser.objects.filter(is_teacher=True, is_member_of_this_school=True).count(),
        # Student chart (last 7 days)
        'attendance_chart_labels':  student_chart['labels'],
        'attendance_chart_present': student_chart['present'],
        'attendance_chart_absent':  student_chart['absent'],
        # Teacher chart (last 7 days)
        'teacher_chart_labels': teacher_chart['labels'],
        'teacher_chart_present': teacher_chart['present'],
        'teacher_chart_absent': teacher_chart['absent'],
        # Student today summary
        'today_present': student_today['present'],
        'today_absent': student_today['absent'],
        'today_total': student_today['total'],
        'today_percentage': student_today['percentage'],
        # Teacher today summary
        'teacher_today_present': teacher_today['present'],
        'teacher_today_absent': teacher_today['absent'],
        'teacher_today_recorded':   teacher_today['total_recorded'],
        'teacher_today_total': teacher_today['total_teachers'],
        'teacher_today_not_marked': teacher_today['not_marked'],
        'teacher_today_percentage': teacher_today['percentage'],
        # Pending users for JS table
        "pending_users_json": pending_users_list,
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

def _get_announcements_for_user(user, limit=5):
    """
    Returns announcements visible to this user based on their role.
    Always includes 'all' target. Adds role-specific ones on top.
    """
    qs = Announcement.objects.select_related('posted_by')
    if not user.is_authenticated:
        return qs.filter(target='all').order_by('-is_pinned', '-created_at')[:limit]
    role_target = None
    if user.is_student:
        role_target = 'students'
    elif user.is_teacher:
        role_target = 'teachers'
    elif user.is_parent:
        role_target = 'parents'
    elif user.is_staff or user.is_superuser:
        role_target = 'staff'
    if role_target:
        qs = qs.filter(
            Q(target='all') | Q(target=role_target)
        )
    else:
        qs = qs.filter(target='all')
    return qs.order_by('-is_pinned', '-created_at')[:limit]

@login_required(login_url='login')
def announcement_list(request):
    """All announcements — staff see everything, others see their own."""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Access denied.')
        return redirect('home')
    announcements = Announcement.objects.select_related(
        'posted_by'
    ).order_by('-is_pinned', '-created_at')
    return render(request, 'pages/announcement_list.html', {
        'announcements': announcements,
    })

@login_required(login_url='login')
def announcement_create(request):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Access denied.')
        return redirect('home')
    if request.method == 'POST':
        title     = request.POST.get('title', '').strip()
        body      = request.POST.get('body', '').strip()
        target    = request.POST.get('target', 'all')
        is_pinned = request.POST.get('is_pinned') == 'on'
        if not title or not body:
            messages.error(request, 'Title and body are required.')
        elif target not in dict(Announcement.TARGET_CHOICES):
            messages.error(request, 'Invalid target audience.')
        else:
            ann = Announcement.objects.create(
                title=title,
                body=body,
                target=target,
                is_pinned=is_pinned,
                posted_by=request.user,
            )
            # Determine recipients
            if target == 'all':
                recipients = CustomUser.objects.filter(
                    is_member_of_this_school=True, is_active=True
                )
            elif target == 'students':
                recipients = CustomUser.objects.filter(
                    is_student=True, is_member_of_this_school=True, is_active=True
                )
            elif target == 'teachers':
                recipients = CustomUser.objects.filter(
                    is_teacher=True, is_member_of_this_school=True, is_active=True
                )
            elif target == 'parents':
                recipients = CustomUser.objects.filter(
                    is_parent=True, is_member_of_this_school=True, is_active=True
                )
            elif target == 'staff':
                recipients = CustomUser.objects.filter(
                    is_staff=True, is_active=True
                )
            else:
                recipients = CustomUser.objects.none()
            # Bulk create — one notification per recipient
            Notification.objects.bulk_create([
                Notification(
                    recipient=user,
                    title=f"New announcement: {title}",
                    body=ann.short_body,
                    notif_type='announcement',
                )
                for user in recipients
                if user != request.user  # don't notify the poster
            ])

            messages.success(request, f'Announcement "{title}" posted.')
            return redirect('announcement_list')
    return render(request, 'pages/announcement_form.html', {
        'targets': Announcement.TARGET_CHOICES,
        'action': 'Create',
    })

@login_required(login_url='login')
def announcement_delete(request, pk):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Access denied.')
        return redirect('home')
    announcement = get_object_or_404(Announcement, pk=pk)
    if request.method == 'POST':
        title = announcement.title
        announcement.delete()
        messages.success(request, f'Announcement "{title}" deleted.')
    return redirect('announcement_list')

@login_required(login_url='login')
def announcement_toggle_pin(request, pk):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Access denied.')
        return redirect('home')
    announcement = get_object_or_404(Announcement, pk=pk)
    if request.method == 'POST':
        announcement.is_pinned = not announcement.is_pinned
        announcement.save()
        state = 'pinned' if announcement.is_pinned else 'unpinned'
        messages.success(request, f'Announcement {state}.')
    return redirect('announcement_list')

# ── NOTIFICATIONS ───
@login_required(login_url='login')
def notification_list(request):
    notifications = request.user.notifications.all()[:50]
    # Mark all as read when the user opens the page
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return render(request, 'pages/notification_list.html', {
        'notifications': notifications,
    })

@login_required(login_url='login')
def notification_mark_read(request, pk):
    notif = get_object_or_404(
        request.user.notifications, pk=pk
    )
    if request.method == 'POST':
        notif.is_read = True
        notif.save()
    return redirect('notification_list')

@login_required(login_url='login')
def notifications_mark_all_read(request):
    if request.method == 'POST':
        request.user.notifications.filter(
            is_read=False
        ).update(is_read=True)
    return redirect('notification_list')