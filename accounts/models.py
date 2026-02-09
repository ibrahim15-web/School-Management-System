from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid
# Create your models here.
class CustomUser(AbstractUser):
    STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
]
    # IDENTITY & AUTHENTICATION
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, unique=True)
    national_id = models.CharField(max_length=20)
    # IMAGES   
    national_id_image = models.ImageField(upload_to='national_id_images/', null=True, blank=True)
    profile_image = models.ImageField(upload_to='profile_images/', null=True, blank=True)
     # SCHOOL ROLES (Business Logic)
     # Note: Users should only have ONE of these set to True
    is_student = models.BooleanField(default=False)
    is_teacher = models.BooleanField(default=False)
    is_parent = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    # APPROVAL SYSTEM
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    is_member_of_this_school = models.BooleanField(default=False)
    rejection_reason = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.username
    
    # HELPER METHODS
    @property
    def display_role(self):
        """Returns human-readable role for templates"""
        if self.is_student:
            return "Student"
        elif self.is_teacher:
            return "Teacher"
        elif self.is_parent:
            return "Parent"
        elif self.is_admin:
            return "Admin"
        elif self.is_staff:
            return "System Admin"  # Django admin
        return "User"  
    @property
    def role_code(self):
        """Returns machine-readable role code"""
        if self.is_student:
            return "student"
        elif self.is_teacher:
            return "teacher"
        elif self.is_parent:
            return "parent"
        elif self.is_admin:
            return "admin"
        return None
    
    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"