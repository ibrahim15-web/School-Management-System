from django.db import models
from django.utils import timezone
import uuid


class Announcement(models.Model):
    TARGET_CHOICES = [
        ('all',      'Everyone'),
        ('students', 'Students only'),
        ('teachers', 'Teachers only'),
        ('parents',  'Parents only'),
        ('staff',    'Staff only'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    title   = models.CharField(max_length=200)
    body    = models.TextField()
    target  = models.CharField(
        max_length=20,
        choices=TARGET_CHOICES,
        default='all',
        help_text="Who can see this announcement",
    )
    is_pinned  = models.BooleanField(
        default=False,
        help_text="Pinned announcements always appear at the top",
    )
    posted_by  = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='announcements',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-created_at']
        verbose_name = "Announcement"
        verbose_name_plural = "Announcements"

    def __str__(self):
        return self.title

    @property
    def short_body(self):
        return self.body[:120] + '...' if len(self.body) > 120 else self.body

class Notification(models.Model):
    TYPE_CHOICES = [
        ('attendance',    'Attendance'),
        ('grade',         'Grade'),
        ('announcement',  'Announcement'),
        ('general',       'General'),
    ]

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient  = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    notif_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='general')
    title      = models.CharField(max_length=200)
    body       = models.CharField(max_length=500)
    is_read    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return f"{self.recipient.username} — {self.title}"

    @classmethod
    def send(cls, recipient, title, body, notif_type='general'):
        """
        Central factory method — always use this to create notifications.
        Keeps all creation logic in one place.
        """
        return cls.objects.create(
            recipient=recipient,
            title=title,
            body=body,
            notif_type=notif_type,
        )