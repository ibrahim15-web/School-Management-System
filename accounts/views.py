from django.shortcuts import render, redirect,HttpResponse
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import transaction
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
import random
import time

User = get_user_model()

def register(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        confirm = request.POST.get("confirm_password")
        user_role = request.POST.get("user_role")
        national_id = request.POST.get("national_id")
        phone_number = request.POST.get("phone_number")
        national_id_image = request.FILES.get("national_id_image")

        if password != confirm:
            messages.error(request, "Passwords do not match")
            return redirect("register")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return redirect("register")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email is already in use")
            return redirect("register")

        if User.objects.filter(national_id=national_id).exists():
            messages.error(request, "National ID already exists")
            return redirect("register")

        if User.objects.filter(phone_number=phone_number).exists():
            messages.error(request, "Phone number already exists")
            return redirect("register")

        if user_role not in ['student', 'teacher', 'parent', 'admin']:
            messages.error(request, "Invalid role selected")
            return redirect("register")

        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                national_id=national_id,
                phone_number=phone_number,
            )

            user.is_active = False
            user.is_member_of_this_school = False
            if national_id_image:
                user.national_id_image = national_id_image

            if user_role == 'student':
                user.is_student = True
            elif user_role == 'teacher':
                user.is_teacher = True
            elif user_role == 'parent':
                user.is_parent = True
            # elif user_role == 'admin':
            #     user.is_staff = True
            user.save()
        messages.success(request, "Your registration request has been sent. Please wait for admin approval.")
        return redirect("waiting_approval")
    return render(request, "accounts/register.html")

def login(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        try:
            user_obj = User.objects.get(email=email)

            if user_obj.status == "rejected":
                messages.error(
                    request,
                    "Your registration request was rejected. Please contact the school administration."
                )
                return redirect("login")

            elif not user_obj.is_member_of_this_school:
                messages.error(request, "Your account is awaiting approval.")
                return redirect("login")
            elif not user_obj.is_active:
                messages.error(request, "Your account is disabled.")

                return redirect("login")

            user = authenticate(request, username=user_obj.username, password=password)

            if user is not None:
                auth_login(request, user)
                return redirect("home")
            else:
                messages.error(request, "Incorrect password")

        except User.DoesNotExist:
            messages.error(request, "Invalid email or password")
            return redirect("login")

    return render(request, "accounts/login.html")


def logout(request):
    auth_logout(request)
    messages.success(request, "You have logged out successfully!")
    return redirect("login")

def waiting_approval(request):
    return render(request, "accounts/waiting_approval.html")

def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get("email")
        try:
            user = User.objects.get(email=email)
            code = str(random.randint(100000, 999999))

            request.session['reset_email'] = email
            request.session['reset_code'] = code
            request.session['reset_expires'] = time.time() + 300  # 5 minutes
            send_mail(
                'Password Reset Code',
                f'Your reset code is: {code}',
                'noreply@yourdomain.com',
                [email],
                fail_silently=False,
            )

        except User.DoesNotExist:
            # We do nothing here, but still redirect to 'verify_code' 
            # so attackers don't know if the email exists.
            pass
        messages.info(request, "If an account exists with that email, a code has been sent.")
        return redirect('verify_code')
    return render(request, 'accounts/forgot_password.html')

def verify_code(request):
    if request.method == "POST":
        input_code = request.POST.get("code")
        stored_code = request.session.get('reset_code')
        expires_at = request.session.get('reset_expires', 0)

        # 2. Check if the code is expired
        if time.time() > expires_at:
            messages.error(request, "The code has expired. Please request a new one.")
            return redirect('forgot_password')

        # 3. Check if the code is correct
        if stored_code and input_code == stored_code:
            request.session['code_verified'] = True
            return redirect('reset_password')
        else:
            messages.error(request, "Invalid code.")

    return render(request, 'accounts/verify_code.html')

def reset_password(request):
    # 1. Security Check: Did they actually pass the verification?
    if not request.session.get('code_verified'):
        messages.error(request, "Please verify your email first.")
        return redirect('forgot_password')

    if request.method == "POST":
        new_password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")
        email = request.session.get('reset_email')

        if len(new_password) < 8:
            messages.error(request, "Password must be at least 8 characters.")
            return render(request, 'accounts/reset_password.html')

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'accounts/reset_password.html')

        try:
            user = User.objects.get(email=email)
            
            # 2. Use transaction.atomic for database safety
            with transaction.atomic():
                user.set_password(new_password)
                user.save()

            # 3. Clean up the session so these keys can't be reused
            keys_to_delete = ['reset_code', 'reset_email', 'reset_expires', 'code_verified']
            for key in keys_to_delete:
                if key in request.session:
                    del request.session[key]

            messages.success(request, "Password reset successful. You can now log in.")
            return redirect('login')

        except User.DoesNotExist:
            messages.error(request, "An error occurred. Please try again.")
            return redirect('forgot_password')

    return render(request, 'accounts/reset_password.html')

def profile(request):
    if not request.user.is_authenticated:
        return redirect('login')

    return render(request, "accounts/profile.html", {"user": request.user})

@login_required
def profile_update(request):
    user = request.user

    if request.method == "POST":
        user.username = request.POST.get("username")
        user.email = request.POST.get("email")
        user.national_id = request.POST.get("national_id")
        user.phone_number = request.POST.get("phone_number")

        if request.FILES.get("national_id_image"):
            user.national_id_image = request.FILES["national_id_image"]
        if request.FILES.get("profile_image"):
            user.profile_image = request.FILES["profile_image"]

        user.save()
        messages.success(request, "Profile updated successfully!")
        return redirect("profile")

    return render(request, "accounts/profile_update.html", {"user": user})

def update_password(request):
    if not request.user.is_authenticated:
        return redirect('login')

    if request.method == "POST":
        current = request.POST.get("current_password")
        new = request.POST.get("new_password")
        confirm = request.POST.get("confirm_password")

        if not request.user.check_password(current):
            messages.error(request, "Current password is incorrect")
            return redirect("update_password")

        if new != confirm:
            messages.error(request, "Passwords do not match")
            return redirect("update_password")

        if len(new) < 8:
            messages.error(request, "Password must be at least 8 characters")
            return redirect("update_password")

        request.user.set_password(new)
        request.user.save()
        update_session_auth_hash(request, request.user)

        messages.success(request, "Password updated successfully!")
        return redirect("profile")

    return render(request, 'accounts/update_password.html')