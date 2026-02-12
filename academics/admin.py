from django.contrib import admin
from .models import AcademicYear, Term, Department, Subject, Class


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