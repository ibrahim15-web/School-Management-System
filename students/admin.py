from django.contrib import admin
from .models import Enrollment


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = [
        'student',
        'class_assigned',
        'academic_year',
        'status',
        'enrollment_date',
        'created_at'
    ]
    list_filter = ['academic_year', 'status', 'class_assigned']
    search_fields = [
        'student__username',
        'student__email',
        'class_assigned__name'
    ]
    readonly_fields = ['enrollment_date', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Enrollment Information', {
            'fields': ('student', 'class_assigned', 'academic_year')
        }),
        ('Status', {
            'fields': ('status', 'enrollment_date')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )