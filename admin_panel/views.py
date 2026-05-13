from django.db import models, transaction
from django.shortcuts import render, get_object_or_404, redirect
from datetime import date
from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from collections import defaultdict

from accounts.models import CustomUser
from academics.models import Class, AcademicYear, TeachingAssignment, Subject, Department, Term, TimetableSlot
from students.models import Enrollment, ParentStudent

# ADMIN GUARD — reusable decorator-like check
def _require_admin(request):
    """Returns True if the user is allowed to use the admin dashboard."""
    return request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)
# STUDENT MANAGEMENT
@login_required(login_url='login')
def admin_students(request):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    try:
        current_year = AcademicYear.objects.get(is_current=True)
    except AcademicYear.DoesNotExist:
        current_year = None
    # All approved students
    students = CustomUser.objects.filter(
        is_student=True,
        is_member_of_this_school=True,
    ).order_by('username')
    # Attach current enrollment to each student so the template can show it
    # We do this efficiently in Python rather than N+1 queries
    if current_year:
        enrollments = Enrollment.objects.filter(
            academic_year=current_year,
            status='active',
        ).select_related('class_assigned').values('student_id', 'class_assigned__name', 'id')

        enrollment_map = {e['student_id']: e for e in enrollments}
    else:
        enrollment_map = {}
    student_list = []
    for s in students:
        student_list.append({
            'user': s,
            'enrollment': enrollment_map.get(s.id),
        })
    context = {
        'student_list': student_list,
        'current_year': current_year,
    }
    return render(request, 'admin-panel/admin_students.html', context)

@login_required(login_url='login')
def admin_assign_student_class(request, user_id):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    student = get_object_or_404(CustomUser, id=user_id, is_student=True)
    try:
        current_year = AcademicYear.objects.get(is_current=True)
    except AcademicYear.DoesNotExist:
        messages.error(request, 'No current academic year is set.')
        return redirect('admin_students')
    # Available classes for this year that are not full
    available_classes = Class.objects.filter(
        academic_year=current_year
    ).order_by('name')
    if request.method == 'POST':
        class_id = request.POST.get('class_id')
        class_obj = get_object_or_404(Class, id=class_id, academic_year=current_year)
        # Check if already enrolled this year
        existing = Enrollment.objects.filter(
            student=student,
            academic_year=current_year,
        ).first()
        if existing:
            # Update existing enrollment to new class
            existing.class_assigned = class_obj
            existing.status = 'active'
            existing.save()
            messages.success(request, f'{student.username} moved to {class_obj.name}.')
        else:
            try:
                Enrollment.objects.create(
                    student=student,
                    class_assigned=class_obj,
                    academic_year=current_year,
                    status='active',
                )
                messages.success(request, f'{student.username} enrolled in {class_obj.name}.')
            except Exception as e:
                messages.error(request, f'Could not enroll: {e}')
        return redirect('admin_students')
    context = {
        'student': student,
        'current_year': current_year,
        'available_classes': available_classes,
    }
    return render(request, 'admin-panel/admin_assign_student.html', context)

@login_required(login_url='login')
def admin_remove_student_class(request, user_id):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    if request.method == 'POST':
        try:
            current_year = AcademicYear.objects.get(is_current=True)
            Enrollment.objects.filter(
                student_id=user_id,
                academic_year=current_year,
            ).update(status='withdrawn')
            messages.success(request, 'Student removed from class.')
        except Exception as e:
            messages.error(request, f'Error: {e}')
    return redirect('admin_students')
# TEACHER MANAGEMENT
@login_required(login_url='login')
def admin_teachers(request):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    try:
        current_year = AcademicYear.objects.get(is_current=True)
    except AcademicYear.DoesNotExist:
        current_year = None
    teachers = CustomUser.objects.filter(
        is_teacher=True,
        is_member_of_this_school=True,
    ).order_by('username')
    # Attach assignment count per teacher for the current year
    teacher_list = []
    for t in teachers:
        if current_year:
            assignments = TeachingAssignment.objects.filter(
                teacher=t,
                academic_year=current_year,
            ).select_related('subject', 'class_assigned')
        else:
            assignments = TeachingAssignment.objects.none()
        teacher_list.append({
            'user': t,
            'assignments': list(assignments),
        })
    context = {
        'teacher_list': teacher_list,
        'current_year': current_year,
    }
    return render(request, 'admin-panel/admin_teachers.html', context)

@login_required(login_url='login')
def admin_assign_teacher(request, user_id):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    teacher = get_object_or_404(CustomUser, id=user_id, is_teacher=True)
    try:
        current_year = AcademicYear.objects.get(is_current=True)
    except AcademicYear.DoesNotExist:
        messages.error(request, 'No current academic year is set.')
        return redirect('admin_teachers')
    classes = Class.objects.filter(academic_year=current_year).prefetch_related('subjects').order_by('name')
    subjects = Subject.objects.all().order_by('name')
    if request.method == 'POST':
        class_id = request.POST.get('class_id')
        subject_id = request.POST.get('subject_id')
        class_obj = get_object_or_404(Class, id=class_id, academic_year=current_year)
        subject_obj = get_object_or_404(Subject, id=subject_id)
        # Subject must be assigned to this class first
        if not class_obj.subjects.filter(id=subject_obj.id).exists():
            messages.error(request, f'{subject_obj.name} is not in {class_obj.name}. Add it to the class first.')
            return redirect('admin_assign_teacher', user_id=user_id)
        _, created = TeachingAssignment.objects.get_or_create(
            teacher=teacher,
            subject=subject_obj,
            class_assigned=class_obj,
            academic_year=current_year,
        )
        if created:
            messages.success(request, f'Assigned {teacher.username} to teach {subject_obj.name} in {class_obj.name}.')
        else:
            messages.info(request, 'This assignment already exists.')
        return redirect('admin_teachers')
    # Current assignments for this teacher this year
    current_assignments = TeachingAssignment.objects.filter(
        teacher=teacher,
        academic_year=current_year,
    ).select_related('subject', 'class_assigned')
    context = {
        'teacher': teacher,
        'current_year': current_year,
        'classes': classes,
        'subjects': subjects,
        'current_assignments': current_assignments,
    }
    return render(request, 'admin-panel/admin_assign_teacher.html', context)

@login_required(login_url='login')
def admin_remove_teacher_assignment(request, user_id, assignment_id):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    if request.method == 'POST':
        TeachingAssignment.objects.filter(
            id=assignment_id,
            teacher_id=user_id,
        ).delete()
        messages.success(request, 'Assignment removed.')
    return redirect('admin_assign_teacher', user_id=user_id)
# CLASS MANAGEMENT
@login_required(login_url='login')
def admin_classes(request):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    try:
        current_year = AcademicYear.objects.get(is_current=True)
    except AcademicYear.DoesNotExist:
        current_year = None
    classes = Class.objects.filter(
        academic_year=current_year
    ).prefetch_related('subjects', 'enrollments').order_by('name') if current_year else []
    context = {
        'classes': classes,
        'current_year': current_year,
    }
    return render(request, 'admin-panel/admin_classes.html', context)

@login_required(login_url='login')
def admin_create_class(request):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')

    try:
        current_year = AcademicYear.objects.get(is_current=True)
    except AcademicYear.DoesNotExist:
        messages.error(request, 'No current academic year is set.')
        return redirect('admin_classes')
    subjects = Subject.objects.all().order_by('name')
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        capacity = request.POST.get('capacity', 30)
        subject_ids = request.POST.getlist('subjects')
        if not name:
            messages.error(request, 'Class name is required.')
            return render(request, 'pages/admin_create_class.html', {
                'current_year': current_year, 'subjects': subjects
            })
        if Class.objects.filter(name=name, academic_year=current_year).exists():
            messages.error(request, f'A class named "{name}" already exists for this year.')
            return render(request, 'pages/admin_create_class.html', {
                'current_year': current_year, 'subjects': subjects
            })
        new_class = Class.objects.create(
            name=name,
            academic_year=current_year,
            capacity=int(capacity),
        )
        if subject_ids:
            new_class.subjects.set(subject_ids)
        messages.success(request, f'Class "{name}" created successfully.')
        return redirect('admin_classes')
    return render(request, 'admin-panel/admin_create_class.html', {
        'current_year': current_year,
        'subjects': subjects,
    })

@login_required(login_url='login')
def admin_class_detail(request, class_id):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    try:
        current_year = AcademicYear.objects.get(is_current=True)
    except AcademicYear.DoesNotExist:
        current_year = None
    class_obj = get_object_or_404(Class, id=class_id)
    subjects = Subject.objects.all().order_by('name')
    if request.method == 'POST':
        # Update subjects assigned to this class
        subject_ids = request.POST.getlist('subjects')
        class_obj.subjects.set(subject_ids)
        messages.success(request, 'Subjects updated.')
        return redirect('admin_class_detail', class_id=class_id)
    enrolled_students = CustomUser.objects.filter(
        enrollments__class_assigned=class_obj,
        enrollments__academic_year=current_year,
        enrollments__status='active',
    ).distinct() if current_year else []
    teachers = TeachingAssignment.objects.filter(
        class_assigned=class_obj,
        academic_year=current_year,
    ).select_related('teacher', 'subject') if current_year else []
    context = {
        'class_obj': class_obj,
        'subjects': subjects,
        'enrolled_students': enrolled_students,
        'teachers': teachers,
        'current_year': current_year,
    }
    return render(request, 'admin-panel/admin_class_detail.html', context)

@login_required(login_url='login')
def admin_delete_class(request, class_id):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    class_obj = get_object_or_404(Class, id=class_id)
    if request.method == 'POST':
        class_name = class_obj.name
        class_obj.delete()  # Cascades to enrollments and teaching assignments
        messages.success(request, f'Class "{class_name}" deleted.')
        return redirect('admin_classes')
    # GET requests go back to detail — no separate confirm page needed
    return redirect('admin_class_detail', class_id=class_id)

@login_required(login_url='login')
def admin_subjects(request):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    subjects = Subject.objects.all().select_related('department').order_by('name')
    context = {'subjects': subjects}
    return render(request, 'admin-panel/admin_subjects.html', context)

@login_required(login_url='login')
def admin_create_subject(request):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    departments = Department.objects.all().order_by('name')
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip().upper()
        department_id = request.POST.get('department_id') or None
        description = request.POST.get('description', '').strip()
        if not name or not code:
            messages.error(request, 'Name and code are required.')
            return render(request, 'admin-panel/admin_subject_form.html', {
                'departments': departments, 'action': 'Create'
            })
        if Subject.objects.filter(name=name).exists():
            messages.error(request, f'A subject named "{name}" already exists.')
            return render(request, 'admin-panel/admin_subject_form.html', {
                'departments': departments, 'action': 'Create'
            })
        if Subject.objects.filter(code=code).exists():
            messages.error(request, f'Code "{code}" is already taken.')
            return render(request, 'admin-panel/admin_subject_form.html', {
                'departments': departments, 'action': 'Create'
            })
        Subject.objects.create(
            name=name,
            code=code,
            department_id=department_id,
            description=description,
        )
        messages.success(request, f'Subject "{name}" created.')
        return redirect('admin_subjects')
    return render(request, 'admin-panel/admin_subject_form.html', {
        'departments': departments,
        'action': 'Create',
    })

@login_required(login_url='login')
def admin_edit_subject(request, subject_id):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    subject = get_object_or_404(Subject, id=subject_id)
    departments = Department.objects.all().order_by('name')
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip().upper()
        department_id = request.POST.get('department_id') or None
        description = request.POST.get('description', '').strip()
        if not name or not code:
            messages.error(request, 'Name and code are required.')
            return render(request, 'admin-panel/admin_subject_form.html', {
                'departments': departments, 'subject': subject, 'action': 'Edit'
            })
        # Check uniqueness excluding current subject
        if Subject.objects.filter(name=name).exclude(id=subject_id).exists():
            messages.error(request, f'A subject named "{name}" already exists.')
            return render(request, 'admin-panel/admin_subject_form.html', {
                'departments': departments, 'subject': subject, 'action': 'Edit'
            })
        if Subject.objects.filter(code=code).exclude(id=subject_id).exists():
            messages.error(request, f'Code "{code}" is already taken.')
            return render(request, 'admin-panel/admin_subject_form.html', {
                'departments': departments, 'subject': subject, 'action': 'Edit'
            })
        subject.name = name
        subject.code = code
        subject.department_id = department_id
        subject.description = description
        subject.save()
        messages.success(request, f'Subject "{name}" updated.')
        return redirect('admin_subjects')
    return render(request, 'admin-panel/admin_subject_form.html', {
        'departments': departments,
        'subject': subject,
        'action': 'Edit',
    })

@login_required(login_url='login')
def admin_delete_subject(request, subject_id):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    subject = get_object_or_404(Subject, id=subject_id)
    if request.method == 'POST':
        subject_name = subject.name
        subject.delete()
        messages.success(request, f'Subject "{subject_name}" deleted.')
        return redirect('admin_subjects')
    return redirect('admin_subjects')

@login_required(login_url='login')
def admin_departments(request):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    departments = Department.objects.all().order_by('name').annotate(
        subject_count=models.Count('subjects'),
        class_count=models.Count('classes'),
    )
    return render(request, 'admin-panel/admin_departments.html', {
        'departments': departments
    })

@login_required(login_url='login')
def admin_create_department(request):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip().upper()
        description = request.POST.get('description', '').strip()
        if not name or not code:
            messages.error(request, 'Name and code are required.')
            return render(request, 'admin-panel/admin_department_form.html', {'action': 'Create'})
        if Department.objects.filter(name=name).exists():
            messages.error(request, f'A department named "{name}" already exists.')
            return render(request, 'admin-panel/admin_department_form.html', {'action': 'Create'})
        if Department.objects.filter(code=code).exists():
            messages.error(request, f'Code "{code}" is already taken.')
            return render(request, 'admin-panel/admin_department_form.html', {'action': 'Create'})
        Department.objects.create(name=name, code=code, description=description)
        messages.success(request, f'Department "{name}" created.')
        return redirect('admin_departments')
    return render(request, 'admin-panel/admin_department_form.html', {'action': 'Create'})

@login_required(login_url='login')
def admin_edit_department(request, department_id):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    department = get_object_or_404(Department, id=department_id)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip().upper()
        description = request.POST.get('description', '').strip()
        if not name or not code:
            messages.error(request, 'Name and code are required.')
            return render(request, 'admin-panel/admin_department_form.html', {
                'department': department, 'action': 'Edit'
            })
        if Department.objects.filter(name=name).exclude(id=department_id).exists():
            messages.error(request, f'A department named "{name}" already exists.')
            return render(request, 'admin-panel/admin_department_form.html', {
                'department': department, 'action': 'Edit'
            })
        if Department.objects.filter(code=code).exclude(id=department_id).exists():
            messages.error(request, f'Code "{code}" is already taken.')
            return render(request, 'admin-panel/admin_department_form.html', {
                'department': department, 'action': 'Edit'
            })
        department.name = name
        department.code = code
        department.description = description
        department.save()
        messages.success(request, f'Department "{name}" updated.')
        return redirect('admin_departments')
    return render(request, 'admin-panel/admin_department_form.html', {
        'department': department,
        'action': 'Edit',
    })
@login_required(login_url='login')
def admin_delete_department(request, department_id):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    department = get_object_or_404(Department, id=department_id)
    if request.method == 'POST':
        name = department.name
        department.delete()
        messages.success(request, f'Department "{name}" deleted.')
        return redirect('admin_departments')
    return redirect('admin_departments')

@login_required(login_url='login')
def admin_update_class_capacity(request, class_id):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    class_obj = get_object_or_404(Class, id=class_id)
    if request.method == 'POST':
        capacity = request.POST.get('capacity', '').strip()
        if not capacity or not capacity.isdigit() or int(capacity) < 1:
            messages.error(request, 'Please enter a valid capacity (minimum 1).')
            return redirect('admin_class_detail', class_id=class_id)
        capacity = int(capacity)
        # Prevent setting capacity below current enrollment
        current_enrollment = class_obj.current_enrollment
        if capacity < current_enrollment:
            messages.error(
                request,
                f'Capacity cannot be less than current enrollment ({current_enrollment} students).'
            )
            return redirect('admin_class_detail', class_id=class_id)
        class_obj.capacity = capacity
        class_obj.save()
        messages.success(request, f'Capacity updated to {capacity}.')
    return redirect('admin_class_detail', class_id=class_id)

@login_required(login_url='login')
def admin_academic_years(request):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    years = AcademicYear.objects.all().order_by('-start_date').annotate(
        class_count=models.Count('classes', distinct=True),
        enrollment_count=models.Count('enrollments', distinct=True),
    )
    return render(request, 'admin-panel/admin_academic_years.html', {
        'years': years,
    })

@login_required(login_url='login')
def admin_create_academic_year(request):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        start_date = request.POST.get('start_date', '').strip()
        end_date = request.POST.get('end_date', '').strip()
        is_current = request.POST.get('is_current') == 'on'
        if not name or not start_date or not end_date:
            messages.error(request, 'Name, start date, and end date are required.')
            return render(request, 'admin-panel/admin_academic_year_form.html', {
                'action': 'Create'
            })
        if AcademicYear.objects.filter(name=name).exists():
            messages.error(request, f'An academic year named "{name}" already exists.')
            return render(request, 'admin-panel/admin_academic_year_form.html', {
                'action': 'Create'
            })
        if start_date >= end_date:
            messages.error(request, 'End date must be after start date.')
            return render(request, 'admin-panel/admin_academic_year_form.html', {
                'action': 'Create'
            })
        year = AcademicYear(
            name=name,
            start_date=start_date,
            end_date=end_date,
            is_current=is_current,
        )
        # AcademicYear.save() already handles unsetting other current years
        year.save()
        messages.success(request, f'Academic year "{name}" created.')
        return redirect('admin_academic_years')
    return render(request, 'admin-panel/admin_academic_year_form.html', {
        'action': 'Create',
    })

@login_required(login_url='login')
def admin_edit_academic_year(request, year_id):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    year = get_object_or_404(AcademicYear, id=year_id)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        start_date = request.POST.get('start_date', '').strip()
        end_date = request.POST.get('end_date', '').strip()
        is_current = request.POST.get('is_current') == 'on'
        if not name or not start_date or not end_date:
            messages.error(request, 'Name, start date, and end date are required.')
            return render(request, 'admin-panel/admin_academic_year_form.html', {
                'year': year, 'action': 'Edit'
            })
        if AcademicYear.objects.filter(name=name).exclude(id=year_id).exists():
            messages.error(request, f'An academic year named "{name}" already exists.')
            return render(request, 'admin-panel/admin_academic_year_form.html', {
                'year': year, 'action': 'Edit'
            })
        if start_date >= end_date:
            messages.error(request, 'End date must be after start date.')
            return render(request, 'admin-panel/admin_academic_year_form.html', {
                'year': year, 'action': 'Edit'
            })
        year.name = name
        year.start_date = start_date
        year.end_date = end_date
        year.is_current = is_current
        year.save()  # save() handles unsetting other current years automatically
        messages.success(request, f'Academic year "{name}" updated.')
        return redirect('admin_academic_years')
    return render(request, 'admin-panel/admin_academic_year_form.html', {
        'year': year,
        'action': 'Edit',
    })

@login_required(login_url='login')
def admin_set_current_year(request, year_id):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    if request.method == 'POST':
        year = get_object_or_404(AcademicYear, id=year_id)
        # Unset all others first, then set this one
        AcademicYear.objects.all().update(is_current=False)
        year.is_current = True
        year.save()
        messages.success(request, f'"{year.name}" is now the current academic year.')
    return redirect('admin_academic_years')

@login_required(login_url='login')
def admin_delete_academic_year(request, year_id):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    year = get_object_or_404(AcademicYear, id=year_id)
    if request.method == 'POST':
        if year.is_current:
            messages.error(request, 'Cannot delete the current academic year. Set another year as current first.')
            return redirect('admin_academic_years')
        name = year.name
        year.delete()
        messages.success(request, f'Academic year "{name}" deleted.')
        return redirect('admin_academic_years')
    return redirect('admin_academic_years')

@login_required(login_url='login')
def admin_terms(request):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    # Group terms by academic year for cleaner display
    years = AcademicYear.objects.prefetch_related('terms').order_by('-start_date')
    return render(request, 'admin-panel/admin_terms.html', {
        'years': years,
    })

@login_required(login_url='login')
def admin_create_term(request):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    years = AcademicYear.objects.all().order_by('-start_date')
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        academic_year_id = request.POST.get('academic_year_id', '').strip()
        start_date = request.POST.get('start_date', '').strip()
        end_date = request.POST.get('end_date', '').strip()
        # ── Validation ──
        if not name or not academic_year_id or not start_date or not end_date:
            messages.error(request, 'All fields are required.')
            return render(request, 'admin-panel/admin_term_form.html', {
                'years': years, 'action': 'Create'
            })
        if start_date >= end_date:
            messages.error(request, 'End date must be after start date.')
            return render(request, 'admin-panel/admin_term_form.html', {
                'years': years, 'action': 'Create'
            })
        academic_year = get_object_or_404(AcademicYear, id=academic_year_id)
        # Term name must be unique within the same academic year
        if Term.objects.filter(name=name, academic_year=academic_year).exists():
            messages.error(request, f'A term named "{name}" already exists for {academic_year.name}.')
            return render(request, 'admin-panel/admin_term_form.html', {
                'years': years, 'action': 'Create'
            })
        # Term dates must be within the academic year range
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        if start < academic_year.start_date or end > academic_year.end_date:
            messages.error(
                request,
                f'Term dates must be within the academic year '
                f'({academic_year.start_date} — {academic_year.end_date}).'
            )
            return render(request, 'admin-panel/admin_term_form.html', {
                'years': years, 'action': 'Create'
            })
        Term.objects.create(
            name=name,
            academic_year=academic_year,
            start_date=start_date,
            end_date=end_date,
        )
        messages.success(request, f'Term "{name}" created for {academic_year.name}.')
        return redirect('admin_terms')
    return render(request, 'admin-panel/admin_term_form.html', {
        'years': years,
        'action': 'Create',
    })

@login_required(login_url='login')
def admin_edit_term(request, term_id):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    term = get_object_or_404(Term, id=term_id)
    years = AcademicYear.objects.all().order_by('-start_date')
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        academic_year_id = request.POST.get('academic_year_id', '').strip()
        start_date = request.POST.get('start_date', '').strip()
        end_date = request.POST.get('end_date', '').strip()
        # ── Validation ──────────────────────────────────────────
        if not name or not academic_year_id or not start_date or not end_date:
            messages.error(request, 'All fields are required.')
            return render(request, 'admin-panel/admin_term_form.html', {
                'term': term, 'years': years, 'action': 'Edit'
            })
        if start_date >= end_date:
            messages.error(request, 'End date must be after start date.')
            return render(request, 'admin-panel/admin_term_form.html', {
                'term': term, 'years': years, 'action': 'Edit'
            })
        academic_year = get_object_or_404(AcademicYear, id=academic_year_id)
        # Check uniqueness excluding the term being edited
        if Term.objects.filter(
            name=name,
            academic_year=academic_year
        ).exclude(id=term_id).exists():
            messages.error(request, f'A term named "{name}" already exists for {academic_year.name}.')
            return render(request, 'admin-panel/admin_term_form.html', {
                'term': term, 'years': years, 'action': 'Edit'
            })
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        if start < academic_year.start_date or end > academic_year.end_date:
            messages.error(
                request,
                f'Term dates must be within the academic year '
                f'({academic_year.start_date} — {academic_year.end_date}).'
            )
            return render(request, 'admin-panel/admin_term_form.html', {
                'term': term, 'years': years, 'action': 'Edit'
            })
        term.name = name
        term.academic_year = academic_year
        term.start_date = start_date
        term.end_date = end_date
        term.save()
        messages.success(request, f'Term "{name}" updated.')
        return redirect('admin_terms')
    return render(request, 'admin-panel/admin_term_form.html', {
        'term': term,
        'years': years,
        'action': 'Edit',
    })

@login_required(login_url='login')
def admin_delete_term(request, term_id):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    term = get_object_or_404(Term, id=term_id)
    if request.method == 'POST':
        name = term.name
        term.delete()
        messages.success(request, f'Term "{name}" deleted.')
        return redirect('admin_terms')
    return redirect('admin_terms')

@login_required(login_url='login')
def admin_users(request):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    # ── Filtering ──
    search = request.GET.get('search', '').strip()
    role_filter = request.GET.get('role', 'all')
    status_filter = request.GET.get('status', 'all')
    users = CustomUser.objects.all().order_by('-date_joined')
    if search:
        users = users.filter(
            models.Q(username__icontains=search) |
            models.Q(email__icontains=search) |
            models.Q(first_name__icontains=search) |
            models.Q(last_name__icontains=search) |
            models.Q(phone_number__icontains=search)
        )
    if role_filter == 'student':
        users = users.filter(is_student=True)
    elif role_filter == 'teacher':
        users = users.filter(is_teacher=True)
    elif role_filter == 'parent':
        users = users.filter(is_parent=True)
    elif role_filter == 'admin':
        users = users.filter(is_admin=True)
    elif role_filter == 'staff':
        users = users.filter(is_staff=True)
    if status_filter == 'active':
        users = users.filter(is_active=True, is_member_of_this_school=True)
    elif status_filter == 'pending':
        users = users.filter(is_member_of_this_school=False, status='pending')
    elif status_filter == 'rejected':
        users = users.filter(status='rejected')
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)
    # ── Pagination ──
    paginator = Paginator(users, 15)  # 15 users per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    context = {
        'page_obj': page_obj,
        'search': search,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'total_count': users.count(),
        # Summary counts for the filter bar
        'count_all': CustomUser.objects.count(),
        'count_students': CustomUser.objects.filter(is_student=True).count(),
        'count_teachers': CustomUser.objects.filter(is_teacher=True).count(),
        'count_pending': CustomUser.objects.filter(
            is_member_of_this_school=False, status='pending'
        ).count(),
    }
    return render(request, 'admin-panel/admin_users.html', context)

@login_required(login_url='login')
def admin_user_detail(request, user_id):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    user = get_object_or_404(CustomUser, id=user_id)
    # Current enrollment if student
    try:
        current_year = AcademicYear.objects.get(is_current=True)
    except AcademicYear.DoesNotExist:
        current_year = None
    enrollment = None
    teaching_assignments = None
    if user.is_student and current_year:
        enrollment = Enrollment.objects.filter(
            student=user,
            academic_year=current_year,
            status='active',
        ).select_related('class_assigned').first()
    if user.is_teacher and current_year:
        teaching_assignments = TeachingAssignment.objects.filter(
            teacher=user,
            academic_year=current_year,
        ).select_related('subject', 'class_assigned')
    context = {
        'viewed_user': user,
        'enrollment': enrollment,
        'teaching_assignments': teaching_assignments,
        'current_year': current_year,
    }
    return render(request, 'admin-panel/admin_user_detail.html', context)

@login_required(login_url='login')
def admin_edit_user(request, user_id):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    user = get_object_or_404(CustomUser, id=user_id)
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        national_id = request.POST.get('national_id', '').strip()
        if not username or not email:
            messages.error(request, 'Username and email are required.')
            return render(request, 'admin-panel/admin_user_edit_form.html', {
                'viewed_user': user
            })
        # Uniqueness checks excluding current user
        if CustomUser.objects.filter(username=username).exclude(id=user_id).exists():
            messages.error(request, 'That username is already taken.')
            return render(request, 'admin-panel/admin_user_edit_form.html', {
                'viewed_user': user
            })
        if CustomUser.objects.filter(email=email).exclude(id=user_id).exists():
            messages.error(request, 'That email is already in use.')
            return render(request, 'admin-panel/admin_user_edit_form.html', {
                'viewed_user': user
            })
        if phone_number and CustomUser.objects.filter(
            phone_number=phone_number
        ).exclude(id=user_id).exists():
            messages.error(request, 'That phone number is already in use.')
            return render(request, 'admin-panel/admin_user_edit_form.html', {
                'viewed_user': user
            })
        user.username = username
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.phone_number = phone_number
        user.national_id = national_id
        user.save()
        messages.success(request, f'User "{username}" updated.')
        return redirect('admin_user_detail', user_id=user_id)
    return render(request, 'admin-panel/admin_user_edit_form.html', {
        'viewed_user': user,
    })

@login_required(login_url='login')
def admin_toggle_user_active(request, user_id):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    if request.method == 'POST':
        user = get_object_or_404(CustomUser, id=user_id)
        # Prevent admin from deactivating their own account
        if user == request.user:
            messages.error(request, 'You cannot deactivate your own account.')
            return redirect('admin_user_detail', user_id=user_id)
        user.is_active = not user.is_active
        user.save()
        state = 'activated' if user.is_active else 'deactivated'
        messages.success(request, f'Account {state} for {user.username}.')
    return redirect('admin_user_detail', user_id=user_id)

@login_required(login_url='login')
def admin_change_user_role(request, user_id):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    if request.method == 'POST':
        user = get_object_or_404(CustomUser, id=user_id)
        new_role = request.POST.get('role', '').strip()
        valid_roles = ['student', 'teacher', 'parent', 'admin']
        if new_role not in valid_roles:
            messages.error(request, 'Invalid role selected.')
            return redirect('admin_user_detail', user_id=user_id)
        # Prevent changing own role
        if user == request.user:
            messages.error(request, 'You cannot change your own role.')
            return redirect('admin_user_detail', user_id=user_id)
        # Reset all roles then set the new one
        user.is_student = False
        user.is_teacher = False
        user.is_parent = False
        user.is_admin = False
        if new_role == 'student':
            user.is_student = True
        elif new_role == 'teacher':
            user.is_teacher = True
        elif new_role == 'parent':
            user.is_parent = True
        elif new_role == 'admin':
            user.is_admin = True
        user.save()
        messages.success(request, f'Role changed to {new_role} for {user.username}.')
    return redirect('admin_user_detail', user_id=user_id)

@login_required(login_url='login')
def admin_delete_user(request, user_id):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    user = get_object_or_404(CustomUser, id=user_id)
    if request.method == 'POST':
        # Prevent admin from deleting their own account
        if user == request.user:
            messages.error(request, 'You cannot delete your own account.')
            return redirect('admin_user_detail', user_id=user_id)
        username = user.username
        user.delete()
        messages.success(request, f'User "{username}" deleted.')
        return redirect('admin_users')
    return redirect('admin_user_detail', user_id=user_id)

@login_required(login_url='login')
def admin_parents(request):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    parents = CustomUser.objects.filter(
        is_parent=True,
        is_member_of_this_school=True,
    ).order_by('username')
    parent_list = []
    for p in parents:
        links = ParentStudent.objects.filter(
            parent=p
        ).select_related('student')
        parent_list.append({
            'user': p,
            'children': [l.student for l in links],
        })
    return render(request, 'admin-panel/admin_parents.html', {
        'parent_list': parent_list,
    })

@login_required(login_url='login')
def admin_assign_parent(request, user_id):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    parent = get_object_or_404(CustomUser, id=user_id, is_parent=True)
    students = CustomUser.objects.filter(
        is_student=True,
        is_member_of_this_school=True,
    ).order_by('username')
    current_links = ParentStudent.objects.filter(
        parent=parent
    ).select_related('student')
    if request.method == 'POST':
        action     = request.POST.get('action')
        student_id = request.POST.get('student_id')
        student    = get_object_or_404(CustomUser, id=student_id, is_student=True)
        if action == 'add':
            _, created = ParentStudent.objects.get_or_create(
                parent=parent, student=student
            )
            if created:
                messages.success(request, f'Linked {student.username} to {parent.username}.')
            else:
                messages.info(request, 'Already linked.')
        elif action == 'remove':
            ParentStudent.objects.filter(
                parent=parent, student=student
            ).delete()
            messages.success(request, 'Link removed.')
        return redirect('admin_assign_parent', user_id=user_id)
    return render(request, 'admin-panel/admin_assign_parent.html', {
        'parent': parent,
        'students': students,
        'current_links': current_links,
    })

# ── TIMETABLE MANAGEMENT ───
@login_required(login_url='login')
def admin_timetable(request):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    try:
        current_year = AcademicYear.objects.get(is_current=True)
    except AcademicYear.DoesNotExist:
        current_year = None
    # Filter by class if requested
    selected_class_id = request.GET.get('class_id', '')
    classes = Class.objects.filter(
        academic_year=current_year
    ).order_by('name') if current_year else []

    slots_qs = TimetableSlot.objects.filter(
        academic_year=current_year
    ).select_related(
        'class_assigned', 'subject', 'teacher'
    ).order_by('class_assigned__name', 'day', 'start_time')

    if selected_class_id:
        slots_qs = slots_qs.filter(class_assigned_id=selected_class_id)
    # Group by class then day
    DAYS = ['monday','tuesday','wednesday','thursday','friday','saturday']
    grouped = defaultdict(lambda: {d: [] for d in DAYS})
    for slot in slots_qs:
        grouped[slot.class_assigned][slot.day].append(slot)
    return render(request, 'admin-panel/admin_timetable.html', {
        'current_year':      current_year,
        'classes':           classes,
        'selected_class_id': selected_class_id,
        'grouped':           dict(grouped),
        'days':              DAYS,
    })

@login_required(login_url='login')
def admin_timetable_create(request):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    try:
        current_year = AcademicYear.objects.get(is_current=True)
    except AcademicYear.DoesNotExist:
        messages.error(request, 'No active academic year.')
        return redirect('admin_timetable')
    classes  = Class.objects.filter(
        academic_year=current_year
    ).order_by('name')
    subjects = Subject.objects.all().order_by('name')
    teachers = CustomUser.objects.filter(
        is_teacher=True,
        is_member_of_this_school=True,
    ).order_by('username')
    if request.method == 'POST':
        class_id   = request.POST.get('class_id')
        subject_id = request.POST.get('subject_id')
        teacher_id = request.POST.get('teacher_id') or None
        day        = request.POST.get('day')
        start_time = request.POST.get('start_time')
        end_time   = request.POST.get('end_time')
        room       = request.POST.get('room', '').strip() or None
        if not all([class_id, subject_id, day, start_time, end_time]):
            messages.error(request, 'All fields except teacher and room are required.')
        elif start_time >= end_time:
            messages.error(request, 'End time must be after start time.')
        else:
            try:
                _, created = TimetableSlot.objects.get_or_create(
                    class_assigned_id=class_id,
                    academic_year=current_year,
                    day=day,
                    start_time=start_time,
                    defaults={
                        'subject_id': subject_id,
                        'teacher_id': teacher_id,
                        'end_time':   end_time,
                        'room':       room,
                    }
                )
                if created:
                    messages.success(request, 'Timetable slot created.')
                else:
                    messages.warning(
                        request,
                        'A slot already exists for that class on that day at that time.'
                    )
                return redirect('admin_timetable')
            except Exception as e:
                messages.error(request, f'Error: {e}')
    return render(request, 'admin-panel/admin_timetable_form.html', {
        'current_year': current_year,
        'classes':      classes,
        'subjects':     subjects,
        'teachers':     teachers,
        'days':         TimetableSlot.DAY_CHOICES,
        'action':       'Create',
    })

@login_required(login_url='login')
def admin_timetable_delete(request, slot_id):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')
    slot = get_object_or_404(TimetableSlot, id=slot_id)
    if request.method == 'POST':
        slot.delete()
        messages.success(request, 'Slot deleted.')
    return redirect('admin_timetable')

@login_required(login_url='login')
def admin_enroll_student(request):
    if not _require_admin(request):
        messages.error(request, 'Access denied.')
        return redirect('home')

    try:
        current_year = AcademicYear.objects.get(is_current=True)
    except AcademicYear.DoesNotExist:
        current_year = None

    classes = Class.objects.filter(
        academic_year=current_year
    ).order_by('name') if current_year else []

    if request.method == 'POST':
        username      = request.POST.get('username',     '').strip()
        email         = request.POST.get('email',        '').strip()
        password      = request.POST.get('password',     '').strip()
        first_name    = request.POST.get('first_name',   '').strip()
        last_name     = request.POST.get('last_name',    '').strip()
        phone_number  = request.POST.get('phone_number', '').strip()
        national_id   = request.POST.get('national_id',  '').strip()
        class_id      = request.POST.get('class_id',     '').strip()
        national_id_image = request.FILES.get('national_id_image')
        profile_image     = request.FILES.get('profile_image')
        # --- Validation ---
        errors = []
        if not username:
            errors.append('Username is required.')
        elif CustomUser.objects.filter(username=username).exists():
            errors.append('That username is already taken.')
        if not email:
            errors.append('Email is required.')
        elif CustomUser.objects.filter(email=email).exists():
            errors.append('That email is already in use.')
        if not password:
            errors.append('Password is required.')
        elif len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if not phone_number:
            errors.append('Phone number is required.')
        elif CustomUser.objects.filter(phone_number=phone_number).exists():
            errors.append('That phone number is already in use.')
        if not national_id:
            errors.append('National ID is required.')
        elif CustomUser.objects.filter(national_id=national_id).exists():
            errors.append('That national ID is already in use.')
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'admin-panel/admin_enroll_student.html', {
                'classes':      classes,
                'current_year': current_year,
            })
        # --- Create the student ---
        try:
            with transaction.atomic():
                user = CustomUser.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    phone_number=phone_number,
                    national_id=national_id,
                )
                user.is_student              = True
                user.is_active               = True
                user.is_member_of_this_school = True
                user.status                  = 'approved'
                if national_id_image:
                    user.national_id_image = national_id_image
                if profile_image:
                    user.profile_image = profile_image
                user.save()
                # Optional class assignment in the same step
                if class_id and current_year:
                    class_obj = Class.objects.get(
                        id=class_id,
                        academic_year=current_year
                    )
                    Enrollment.objects.create(
                        student=user,
                        class_assigned=class_obj,
                        academic_year=current_year,
                        status='active',
                    )
                    messages.success(
                        request,
                        f'Student "{username}" created and enrolled in {class_obj.name}.'
                    )
                else:
                    messages.success(
                        request,
                        f'Student "{username}" created successfully. You can assign a class from the students list.'
                    )
            return redirect('admin_students')
        except Exception as e:
            messages.error(request, f'Something went wrong: {e}')
    return render(request, 'admin-panel/admin_enroll_student.html', {
        'classes':      classes,
        'current_year': current_year,
    })