from django.urls import path
from . import views

urlpatterns = [
    # ── Student management ──
    path('students/', views.admin_students, name='admin_students'),
    path('students/<uuid:user_id>/assign-class/', views.admin_assign_student_class, name='admin_assign_student_class'),
    path('students/<uuid:user_id>/remove-class/', views.admin_remove_student_class, name='admin_remove_student_class'),
    # ── Teacher management ──
    path('teachers/', views.admin_teachers, name='admin_teachers'),
    path('teachers/<uuid:user_id>/assign/', views.admin_assign_teacher, name='admin_assign_teacher'),
    path('teachers/<uuid:user_id>/remove-assignment/<uuid:assignment_id>/', views.admin_remove_teacher_assignment, name='admin_remove_teacher_assignment'),
    # ── Class management ──
    path('classes/', views.admin_classes, name='admin_classes'),
    path('classes/create/', views.admin_create_class, name='admin_create_class'),
    path('classes/<uuid:class_id>/', views.admin_class_detail, name='admin_class_detail'),
    path('classes/<uuid:class_id>/update-capacity/', views.admin_update_class_capacity, name='admin_update_class_capacity'),
    path('classes/<uuid:class_id>/delete/', views.admin_delete_class, name='admin_delete_class'),
    # ── Subjects management ──
    path('subjects/', views.admin_subjects, name='admin_subjects'),
    path('subjects/create/', views.admin_create_subject, name='admin_create_subject'),
    path('subjects/<uuid:subject_id>/edit/', views.admin_edit_subject, name='admin_edit_subject'),
    path('subjects/<uuid:subject_id>/delete/', views.admin_delete_subject, name='admin_delete_subject'),
    # ── Departments management ──
    path('departments/', views.admin_departments, name='admin_departments'),
    path('departments/create/', views.admin_create_department, name='admin_create_department'),
    path('departments/<uuid:department_id>/edit/', views.admin_edit_department, name='admin_edit_department'),
    path('departments/<uuid:department_id>/delete/', views.admin_delete_department, name='admin_delete_department'),
    # ── Academic year management ──
    path('academic-years/', views.admin_academic_years, name='admin_academic_years'),
    path('academic-years/create/', views.admin_create_academic_year, name='admin_create_academic_year'),
    path('academic-years/<uuid:year_id>/edit/', views.admin_edit_academic_year, name='admin_edit_academic_year'),
    path('academic-years/<uuid:year_id>/set-current/', views.admin_set_current_year, name='admin_set_current_year'),
    path('academic-years/<uuid:year_id>/delete/', views.admin_delete_academic_year, name='admin_delete_academic_year'),
    # ── Term management ──
    path('terms/', views.admin_terms, name='admin_terms'),
    path('terms/create/', views.admin_create_term, name='admin_create_term'),
    path('terms/<uuid:term_id>/edit/', views.admin_edit_term, name='admin_edit_term'),
    path('terms/<uuid:term_id>/delete/', views.admin_delete_term, name='admin_delete_term'),
    # ── User management ──
    path('users/', views.admin_users, name='admin_users'),
    path('users/<uuid:user_id>/', views.admin_user_detail, name='admin_user_detail'),
    path('users/<uuid:user_id>/edit/', views.admin_edit_user, name='admin_edit_user'),
    path('users/<uuid:user_id>/toggle-active/', views.admin_toggle_user_active, name='admin_toggle_user_active'),
    path('users/<uuid:user_id>/change-role/', views.admin_change_user_role, name='admin_change_user_role'),
    path('users/<uuid:user_id>/delete/', views.admin_delete_user, name='admin_delete_user'),
]
