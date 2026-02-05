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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    national_id = models.CharField(max_length=20)   
    national_id_image = models.ImageField(upload_to='national_id_images/', null=True, blank=True)
    profile_image = models.ImageField(upload_to='profile_images/', null=True, blank=True)
    phone_number = models.CharField(max_length=15, unique=True)
    is_student = models.BooleanField(default=False)
    is_teacher = models.BooleanField(default=False)
    is_parent = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    is_member_of_this_school = models.BooleanField(default=False)
    rejection_reason = models.TextField(null=True, blank=True)

    

    def __str__(self):
        return self.username
    
