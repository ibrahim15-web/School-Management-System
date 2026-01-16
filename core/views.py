from django.shortcuts import redirect, render, get_object_or_404
from accounts.models import CustomUser
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.contrib import messages
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
    'is_teacher',
))

    # Convert UUIDs and Dates to strings for JSON compatibility
    for user in pending_users_list:
        user['id'] = str(user['id'])
        user['date_joined'] = user['date_joined'].strftime('%Y-%m-%dT%H:%M:%S')
        user['full_name'] = f"{user['first_name']} {user['last_name']}".strip() or user['username']

    context = {
        "pending_count": pending_users_queryset.count(),
        "pending_students": pending_users_queryset.filter(is_student=True).count(),
        "pending_teachers": pending_users_queryset.filter(is_teacher=True).count(),
        "total_students": CustomUser.objects.filter(is_student=True, is_member_of_this_school=True).count(),
        "total_teachers": CustomUser.objects.filter(is_teacher=True, is_member_of_this_school=True).count(),
        "pending_users_json": pending_users_list, # For JS
    }
    return render(request, 'pages/admin_dashboard.html', context)
@login_required
def update_user_status(request):
    """API Endpoint to approve or reject users via AJAX with role support"""
    if request.method == "POST" and request.user.is_staff:
        data = json.loads(request.body)

        user_ids = data.get("user_ids", [])
        action = data.get("action")
        roles = data.get("roles", {})

        for user_id in user_ids:
            user = CustomUser.objects.get(id=user_id)

            if action == "approve":
                role = roles.get(user_id)

                # Reset roles
                user.is_student = False
                user.is_teacher = False
                user.is_parent = False

                # Apply selected role
                if role == "student":
                    user.is_student = True
                elif role == "teacher":
                    user.is_teacher = True

                user.status = "approved"
                user.is_active = True
                user.is_member_of_this_school = True

            elif action == "reject":
                user.status = "rejected"
                user.is_active = False
                user.is_member_of_this_school = False

            user.save()

        return JsonResponse({"status": "success"})

    return JsonResponse({"status": "error"}, status=400)
