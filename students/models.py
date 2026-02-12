"""
students/models.py (Phase 2 — Enrollment Layer)

This model connects approved students to classes within an academic year.
Students inherit subjects from their assigned class.
"""

# Django imports
from django.db import models
from django.core.exceptions import ValidationError
import uuid

# Local imports
from accounts.models import CustomUser
from academics.models import AcademicYear, Class


class Enrollment(models.Model):
    """
    Enrollment Model — Connects Students to Classes per Academic Year
    
    WHY THIS MODEL EXISTS:
    - Students change classes every academic year
    - We need enrollment history
    - We need status tracking (active, withdrawn, graduated)
    - We must enforce class capacity
    - We must prevent duplicate enrollment in same academic year
    
    BUSINESS RULES:
    1. Student must have is_student=True
    2. Student must be approved
    3. One enrollment per student per academic year
    4. Class must belong to the same academic year
    5. Class capacity must not be exceeded
    
    RELATIONSHIPS:
    - Belongs to one Student (CustomUser where is_student=True)
    - Belongs to one Class (which has subjects)
    - Belongs to one AcademicYear
    
    EXAMPLE:
    John Doe → Grade 10-A (2024-2025) [active]
    """

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('withdrawn', 'Withdrawn'),
        ('graduated', 'Graduated'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    student = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='enrollments',
        limit_choices_to={'is_student': True},
        help_text="Student being enrolled"
    )

    class_assigned = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name='enrollments',
        help_text="Class the student is assigned to"
    )

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='enrollments',
        help_text="Academic year of enrollment"
    )

    enrollment_date = models.DateField(
        auto_now_add=True,
        help_text="Date when student was enrolled"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        help_text="Current enrollment status"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [['student', 'academic_year']]
        verbose_name = "Enrollment"
        verbose_name_plural = "Enrollments"
        indexes = [
            models.Index(fields=['student', 'academic_year']),
            models.Index(fields=['class_assigned', 'status']),
        ]

    def __str__(self):
        return f"{self.student.username} → {self.class_assigned.name} ({self.academic_year.name})"

    def clean(self):
        """
        Model-level validation enforcing business rules
        """

        # 1️⃣ Ensure student is actually a student
        if not self.student.is_student:
            raise ValidationError({
                'student': "Selected user is not a student."
            })

        # 2️⃣ Ensure student is approved
        if self.student.status != 'approved':
            raise ValidationError({
                'student': "Student must be approved before enrollment."
            })

        # 3️⃣ Ensure student is a member of the school
        if not self.student.is_member_of_this_school:
            raise ValidationError({
                'student': "Student must be a member of this school."
            })

        # 4️⃣ Ensure academic year matches class academic year
        if self.class_assigned.academic_year != self.academic_year:
            raise ValidationError({
                'academic_year': "Class academic year must match enrollment academic year."
            })

        # 5️⃣ Enforce class capacity (only when status is active)
        if self.status == 'active':
            current_active_enrollments = Enrollment.objects.filter(
                class_assigned=self.class_assigned,
                academic_year=self.academic_year,
                status='active'
            )

            # Exclude self when updating existing record
            if self.pk:
                current_active_enrollments = current_active_enrollments.exclude(pk=self.pk)

            if current_active_enrollments.count() >= self.class_assigned.capacity:
                raise ValidationError({
                    'class_assigned': f"Class capacity ({self.class_assigned.capacity}) has been reached."
                })

    def save(self, *args, **kwargs):
        """Enforce validation before saving"""
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def subjects(self):
        """
        Get subjects for this enrollment (inherited from class).
        
        Students automatically inherit all subjects from their assigned class.
        For custom subject selection, create a separate StudentSubject model.
        """
        return self.class_assigned.subjects.all()

    @property
    def department(self):
        """Get department (if class is streamed by department)"""
        return self.class_assigned.department