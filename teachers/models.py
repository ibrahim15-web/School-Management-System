import uuid
from django.db import models
from accounts.models import CustomUser
from academics.models import Class, AcademicYear

class Attendance(models.Model):   
    STATUS_PRESENT = 'present'
    STATUS_ABSENT = 'absent'
    STATUS_CHOICES = [
        (STATUS_PRESENT, 'Present'),
        (STATUS_ABSENT, 'Absent'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    student = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='student_attendance',
        limit_choices_to={'is_student': True}
    )
    class_assigned = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    date = models.DateField(db_index=True)  # indexed for date-range queries
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_PRESENT,
        db_index=True   # indexed for filtering by status
    )
    marked_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='marked_attendance'
    )
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='updated_attendance'
    )
    created_at = models.DateTimeField(auto_now_add=True)  # restored
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'class_assigned', 'academic_year', 'date')
        indexes = [
            # Covers: "give me all records for this class in this date range"
            models.Index(fields=['class_assigned', 'date']),
            # Covers: "give me all records for this student"
            models.Index(fields=['student', 'date']),
            # Covers: "give me last 7 days school-wide"
            models.Index(fields=['date', 'status']),
        ]
    def __str__(self):
        return f"{self.student} - {self.date} - {self.status}"

class TeacherAttendance(models.Model):
    STATUS_PRESENT = 'present'
    STATUS_ABSENT = 'absent'
    STATUS_CHOICES = [
        (STATUS_PRESENT, 'Present'),
        (STATUS_ABSENT, 'Absent'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    teacher = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='teacher_attendance_records',
        limit_choices_to={'is_teacher': True},
        help_text="Teacher whose attendance is being recorded"
    )

    date = models.DateField(
        db_index=True,
        help_text="Date of attendance"
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_PRESENT,
        db_index=True
    )

    marked_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='marked_teacher_attendance',
        help_text="Admin who recorded this entry"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('teacher', 'date')
        ordering = ['-date', 'teacher__username']
        verbose_name = "Teacher Attendance"
        verbose_name_plural = "Teacher Attendance"
        indexes = [
            models.Index(fields=['date', 'status']),
            models.Index(fields=['teacher', 'date']),
        ]

    def __str__(self):
        return f"{self.teacher.username} — {self.date} — {self.get_status_display()}"