from django.urls import path
from .views import *

urlpatterns = [
    path('teacher_dashboard/',teacher_dashboard , name='teacher_dashboard'),
    path('assignment/<uuid:assignment_id>/students/', teacher_students_view, name='teacher_students'),
    path('students/', teacher_all_students, name='teacher_all_students'),
    path('attendance/', teacher_attendance, name='teacher_attendance'),
    path('attendance/<uuid:assignment_id>/', mark_attendance, name='mark_attendance'),
    # Admin-only: mark daily attendance for all teachers
    path('teacher-attendance/', mark_teacher_attendance, name='mark_teacher_attendance'),
    path('grades/', teacher_grades, name='teacher_grades'),
    path('schedule/', teacher_schedule, name='teacher_schedule'),
]