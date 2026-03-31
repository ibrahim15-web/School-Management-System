from django.contrib import admin
from .models import (
    AcademicYear, 
    Term, 
    Department, 
    Subject, 
    Class,
    TeachingAssignment,
)


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date', 'is_current']
    list_filter = ['is_current']
    search_fields = ['name']
    ordering = ['-start_date']


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ['name', 'academic_year', 'start_date', 'end_date']
    list_filter = ['academic_year']
    search_fields = ['name']
    ordering = ['academic_year', 'start_date']


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'created_at']
    search_fields = ['name', 'code']
    ordering = ['name']


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'department']
    list_filter = ['department']
    search_fields = ['name', 'code']
    ordering = ['name']


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ['name', 'academic_year', 'department', 'capacity', 'current_enrollment']
    list_filter = ['academic_year', 'department']
    search_fields = ['name']
    filter_horizontal = ['subjects']  # Better UI for ManyToMany
    ordering = ['academic_year', 'name']
    
    def current_enrollment(self, obj):
        return obj.current_enrollment
    current_enrollment.short_description = 'Enrolled'
@admin.register(TeachingAssignment)
class TeachingAssignmentAdmin(admin.ModelAdmin):
    """
    Admin interface for Teaching Assignments
    
    Features:
    - View all assignments with key details
    - Filter by academic year, class, subject
    - Search by teacher name/username
    - Quick access to related objects
    """
    
    list_display = [
        'get_teacher_name',
        'subject',
        'class_assigned',
        'academic_year',
        'student_count',
        'assigned_at',
    ]
    
    list_filter = [
        'academic_year',
        'class_assigned',
        'subject',
    ]
    
    search_fields = [
        'teacher__username',
        'teacher__first_name',
        'teacher__last_name',
        'teacher__email',
        'subject__name',
        'class_assigned__name',
    ]
    
    readonly_fields = [
        'assigned_at',
        'created_at',
        'updated_at',
        'student_count',
    ]
    
    ordering = ['-academic_year', 'class_assigned', 'subject']
    
    fieldsets = (
        ('Assignment Details', {
            'fields': (
                'teacher',
                'subject',
                'class_assigned',
                'academic_year'
            )
        }),
        ('Information', {
            'fields': (
                'student_count',
                'assigned_at',
            )
        }),
        ('Metadata', {
            'fields': (
                'created_at',
                'updated_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    # Custom column methods
    def get_teacher_name(self, obj):
        """Display teacher's full name or username"""
        return obj.teacher.get_full_name() or obj.teacher.username
    get_teacher_name.short_description = 'Teacher'
    get_teacher_name.admin_order_field = 'teacher__last_name'
    
    def student_count(self, obj):
        """Display number of students in this assignment"""
        return obj.student_count
    student_count.short_description = 'Students'
    
    # Optimize queries
    def get_queryset(self, request):
        """
        Optimize database queries by selecting related objects
        """
        queryset = super().get_queryset(request)
        return queryset.select_related(
            'teacher',
            'subject',
            'class_assigned',
            'academic_year'
        )