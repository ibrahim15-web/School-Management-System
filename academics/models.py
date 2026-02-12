"""
Academic Structure Foundation Models
======================================

Core entities for school academic organization:
- AcademicYear: Yearly container (2024-2025)
- Term: Subdivisions of academic year (Fall, Spring)
- Department: Academic divisions (Science, Arts)
- Subject: Courses/subjects taught (Math, Physics)
- Class: Student groupings (Grade 10-A)

Design Philosophy:
- Minimal but realistic
- UUID primary keys
- Proper relationships
- Future-proof
- No premature optimization
"""

from django.db import models
import uuid
from django.core.exceptions import ValidationError


class AcademicYear(models.Model):
    """
    Represents an academic year (e.g., 2024-2025).
    
    WHY: Schools operate in yearly cycles. All academic activity
    is timestamped to a year.
    
    RELATIONSHIPS:
    - Has many Terms (Fall 2024, Spring 2025)
    - Has many Classes (Grade 10-A exists per year)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True, help_text="e.g., 2024-2025")
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(
        default=False,
        help_text="Only one academic year should be current at a time"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name = "Academic Year"
        verbose_name_plural = "Academic Years"

    def __str__(self):
        return self.name

    def clean(self):
        """Validate that end_date is after start_date"""
        if self.end_date and self.start_date and self.end_date <= self.start_date:
            raise ValidationError("End date must be after start date")

    def save(self, *args, **kwargs):
        """Ensure only one academic year is current"""
        if self.is_current:
            # Set all other academic years to not current
            AcademicYear.objects.filter(is_current=True).update(is_current=False)
        super().save(*args, **kwargs)


class Term(models.Model):
    """
    Represents a term/semester within an academic year.
    
    WHY: Academic years are divided into terms (Fall, Spring, etc.).
    Used later for attendance tracking, exam periods, grading cycles.
    
    RELATIONSHIPS:
    - Belongs to one AcademicYear
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='terms'
    )
    name = models.CharField(max_length=50, help_text="e.g., Fall Term, Spring Term")
    start_date = models.DateField()
    end_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['academic_year', 'start_date']
        unique_together = [['academic_year', 'name']]
        verbose_name = "Term"
        verbose_name_plural = "Terms"

    def __str__(self):
        return f"{self.name} ({self.academic_year.name})"

    def clean(self):
        """Validate term dates are within academic year"""
        if self.end_date and self.start_date and self.end_date <= self.start_date:
            raise ValidationError("End date must be after start date")
        
        if self.academic_year:
            if self.start_date < self.academic_year.start_date:
                raise ValidationError("Term cannot start before academic year")
            if self.end_date > self.academic_year.end_date:
                raise ValidationError("Term cannot end after academic year")


class Department(models.Model):
    """
    Represents an academic department/faculty.
    
    WHY: Schools organize subjects by discipline (Science, Arts, Commerce).
    Departments are relatively permanent (persist across years).
    
    RELATIONSHIPS:
    - Has many Subjects
    - Optionally has many Classes (for streaming schools)
    
    EXAMPLES:
    - Science Department
    - Arts & Humanities
    - Commerce & Business Studies
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(
        max_length=10,
        unique=True,
        help_text="Short code (e.g., SCI, ART, COM)"
    )
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Department"
        verbose_name_plural = "Departments"

    def __str__(self):
        return self.name


class Subject(models.Model):
    """
    Represents a subject/course taught in the school.
    
    WHY: This is what is actually taught (Math, Physics, English).
    Subjects are relatively static but organized by department.
    
    RELATIONSHIPS:
    - Belongs to one Department (optional - some subjects are cross-departmental)
    - Taught in many Classes (ManyToMany through Class.subjects)
    
    FUTURE:
    - Will be linked to Teachers (Phase 3)
    - Will be linked to Students individually (for electives)
    
    EXAMPLES:
    - Mathematics (Science Dept)
    - Physics (Science Dept)
    - English Literature (Arts Dept)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(
        max_length=10,
        unique=True,
        help_text="Short code (e.g., MATH101, PHYS201)"
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subjects',
        help_text="Optional - some subjects are cross-departmental"
    )
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Subject"
        verbose_name_plural = "Subjects"

    def __str__(self):
        if self.department:
            return f"{self.name} ({self.department.code})"
        return self.name


class Class(models.Model):
    """
    Represents a class/section (e.g., Grade 10-A, Year 11 Science).
    
    WHY: Students are grouped into classes for teaching.
    Classes exist per academic year (10-A in 2024 ≠ 10-A in 2025).
    
    RELATIONSHIPS:
    - Belongs to one AcademicYear (required)
    - Optionally belongs to one Department (for streaming schools)
    - Studies many Subjects (ManyToMany)
    
    FUTURE:
    - Will have many Students (Phase 2: Enrollment)
    - Will have Teachers assigned per subject (Phase 3)
    
    EXAMPLES:
    - "Grade 10-A" (general class, no department)
    - "Year 11 Science Section" (belongs to Science Dept)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='classes'
    )
    name = models.CharField(
        max_length=100,
        help_text="e.g., Grade 10-A, Year 11 Science"
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='classes',
        help_text="Optional - only for schools with department-based streaming"
    )
    subjects = models.ManyToManyField(
        Subject,
        related_name='classes',
        blank=True,
        help_text="Subjects offered to this class"
    )
    capacity = models.PositiveIntegerField(
        default=30,
        help_text="Maximum number of students"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['academic_year', 'name']
        unique_together = [['academic_year', 'name']]
        verbose_name = "Class"
        verbose_name_plural = "Classes"

    def __str__(self):
        return f"{self.name} ({self.academic_year.name})"

    @property
    def current_enrollment(self):
        from students.models import Enrollment

        return Enrollment.objects.filter(
            class_assigned=self,
            academic_year=self.academic_year,
            status='active'
        ).count()


    @property
    def is_full(self):
        """Check if class has reached capacity"""
        return self.current_enrollment >= self.capacity