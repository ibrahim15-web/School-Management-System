from django.contrib import admin
from .models import Attendance, TeacherAttendance


@admin.register(TeacherAttendance)
class TeacherAttendanceAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'date', 'status', 'marked_by', 'updated_at']
    list_filter = ['status', 'date']
    search_fields = ['teacher__username', 'teacher__first_name', 'teacher__last_name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-date', 'teacher__username']
 
    fieldsets = (
        ('Attendance Record', {
            'fields': ('teacher', 'date', 'status')
        }),
        ('Audit', {
            'fields': ('marked_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
 
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('teacher', 'marked_by')