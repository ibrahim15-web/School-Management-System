from django.shortcuts import render
from accounts.models import CustomUser
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
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

# Get an instance of a logger
logger = logging.getLogger(__name__)
@login_required
def process_pending_registrations(request):
    """API Endpoint to approve or reject users via AJAX"""
    if request.method == 'POST' and request.user.is_staff:
        try:
            data = json.loads(request.body)
            action = data.get('action') # 'approve' or 'reject'
            users_data = data.get('users', [])
            email_messages = []
            if action == 'approve':
                with transaction.atomic():
                    for item in users_data:
                        try:
                            user = CustomUser.objects.get(id=item['id'])
                            role = item.get("role")
                            ROLE_MAP = {
                                'student': 'is_student',
                                'teacher': 'is_teacher',
                                'parent': 'is_parent',
                                'admin': 'is_staff',}
                            # 1. Reset all role flags first (Ensures ONLY ONE role)
                            user.is_student = False
                            user.is_teacher = False
                            user.is_parent = False
                            user.is_staff = False
                            # Assign role safely
                            if role in ROLE_MAP:
                                setattr(user, ROLE_MAP[role], True)
                            else:
                                raise ValueError("Invalid role")
                            user.is_member_of_this_school = True
                            user.is_active = True
                            user.status = 'approved'
                            user.save()

                            if user.email:
                                email_messages.append((
                                    "Your account has been approved",
                                    f"Hi {user.username}, your account has been approved as a {role}.\nSo now you can log in.",
                                    settings.EMAIL_HOST_USER,
                                    [user.email]
                                ))

                        except CustomUser.DoesNotExist:
                            continue
                
            elif action == 'reject':
                reason = data.get('reason', '').strip()
                with transaction.atomic():
                    for item in users_data:
                        try:
                            user = CustomUser.objects.get(id=item['id'])
                            # Clear roles
                            user.is_student = False
                            user.is_teacher = False
                            user.is_parent = False
                            user.is_staff = False

                            user.is_active = False
                            user.is_member_of_this_school = False
                            user.status = 'rejected'
                            
                            if hasattr(user, 'rejection_reason'):
                                user.rejection_reason = reason

                            user.save()

                            if user.email:
                                message = f"Hi {user.username}, your registration request has been rejected."
                                if reason:
                                    message += f"\n\nReason: {reason}"

                                email_messages.append((
                                    "Registration Request Rejected",
                                    message,
                                    settings.EMAIL_HOST_USER,
                                    [user.email]
                                ))

                        except CustomUser.DoesNotExist:
                            continue
            else:
                return JsonResponse({'status': 'error', 'message': 'Invalid action'}, status=400)
            
            if email_messages:
                try:
                    send_mass_mail(email_messages, fail_silently=False)
                except Exception as e:
                    logger.error(f"Email failed to send: {e}")
                    return JsonResponse({'status': 'partial_success', 'message': 'Users updated, but emails failed to send.'})

            return JsonResponse({'status': 'success'})
        except (ValueError, TypeError, json.JSONDecodeError, KeyError):
            return JsonResponse({'status': 'error', 'message': 'Invalid data format'}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Unauthorized or invalid method'}, status=403)    