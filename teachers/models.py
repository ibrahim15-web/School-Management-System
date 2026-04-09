from django.db import models
from accounts.models import CustomUser
from academics.models import *

class Attendance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    student = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='student_attendance'
    )

    class_assigned = models.ForeignKey(Class, on_delete=models.CASCADE)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)

    date = models.DateField()

    status = models.CharField(
        max_length=10,
        choices=[('present', 'Present'), ('absent', 'Absent')],
        default='present'
    )

    marked_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='marked_attendance'
    )

    updated_at = models.DateTimeField(auto_now=True)

    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='updated_attendance'
    )

    class Meta:
        unique_together = ('student', 'class_assigned', 'academic_year', 'date')

    def __str__(self):
        return f"{self.student} - {self.date} - {self.status}"