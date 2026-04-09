from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.timezone import now
from .models import *
from academics.models import *
from accounts.models import CustomUser

@login_required(login_url='login')
def teacher_dashboard(request):
    """
    Teacher Dashboard
    Shows teacher's current teaching load:
    - Assignments
    - Classes
    - Students
    - Quick actions
    """
    if not request.user.is_teacher:
        messages.error(request, 'Access denied. This page is for teachers only.')
        return redirect('home')
    try:
        current_year = AcademicYear.objects.get(is_current=True)
    except AcademicYear.DoesNotExist:
        current_year = None
        messages.warning(request, 'No current academic year is set. Please contact administration.')
    if current_year:
        assignments = request.user.teaching_assignments.filter(
            academic_year=current_year
        ).select_related(
            'subject',
            'class_assigned',
            'class_assigned__department',
            'academic_year'
        ).order_by('class_assigned__name', 'subject__name')
    else:
        assignments = request.user.teaching_assignments.none()
    
    total_assignments = assignments.count()
    total_classes = assignments.values('class_assigned').distinct().count()
    total_subjects = assignments.values('subject').distinct().count()
    total_students = sum(assignment.student_count for assignment in assignments)
    context = {
        'teacher': request.user,
        'current_year': current_year,
        'assignments': assignments,
        'total_classes': total_classes,
        'total_subjects': total_subjects,
        'total_students': total_students,
        'total_assignments': total_assignments,
    } 
    return render(request, 'teachers/teacher_dashboard.html', context)
@login_required(login_url='login')
def teacher_students_view(request, assignment_id):
    if not request.user.is_teacher:
        messages.error(request, 'Access denied. This page is for teachers only.')
        return redirect('home')

    assignment = get_object_or_404(
        request.user.teaching_assignments.select_related(
            'class_assigned', 'subject'
        ),
        id=assignment_id
    )

    students = (
    CustomUser.objects
    .filter(
        enrollments__class_assigned=assignment.class_assigned,
        enrollments__academic_year=assignment.academic_year,
        enrollments__status='active'
    )
    .only('id', 'username', 'first_name', 'last_name', 'email')
    .distinct())

    context = {
        'assignment': assignment,
        'students': students,
    }
    return render(request, 'teachers/student_list.html', context)

@login_required(login_url='login')
def teacher_all_students(request):
    if not request.user.is_teacher:
        messages.error(request, 'Access denied.')
        return redirect('home')

    try:
        current_year = AcademicYear.objects.get(is_current=True)
    except AcademicYear.DoesNotExist:
        current_year = None

    if current_year:
        assignments = request.user.teaching_assignments.filter(
            academic_year=current_year
        ).select_related(
            'class_assigned',
            'subject'
        )
    else:
        assignments = request.user.teaching_assignments.none()

    context = {
        'assignments': assignments
    }

    return render(request, 'teachers/students_all.html', context)

@login_required(login_url='login')
def teacher_attendance(request):
    if not request.user.is_teacher:
        messages.error(request, "Access denied. Teachers only.")
        return redirect('home')
    assignments = request.user.teaching_assignments.select_related(
        'class_assigned', 'subject'
    )

    return render(request, 'teachers/attendance.html', {
        'assignments': assignments
    })
@login_required(login_url='login')
def mark_attendance(request, assignment_id):
    if not request.user.is_teacher:
        messages.error(request, "Access denied. Teachers only.")
        return redirect('home')
    assignment = get_object_or_404(
        request.user.teaching_assignments.select_related(
            'class_assigned', 'academic_year'
        ),
        id=assignment_id
    )

    students = CustomUser.objects.filter(
        enrollments__class_assigned=assignment.class_assigned,
        enrollments__academic_year=assignment.academic_year,
        enrollments__status='active'
    ).distinct()

    if request.method == 'POST':
        date = request.POST.get('date')

        if not date:
            messages.error(request, "Please select a date.")
            return redirect('mark_attendance', assignment_id=assignment.id)

        try:
            for student in students:
                status = request.POST.get(f'student_{student.id}')

                if status not in ['present', 'absent']:
                    raise ValueError(f"Invalid status for {student}")

                Attendance.objects.update_or_create(
                    student=student,
                    class_assigned=assignment.class_assigned,
                    academic_year=assignment.academic_year,
                    date=date,
                    defaults={
                        'status': status,
                        'marked_by': request.user,
                        'updated_by': request.user,
                    }
                )

            messages.success(request, "Attendance saved successfully!")
            return redirect('teacher_attendance')

        except Exception as e:
            messages.error(request, "Error while saving attendance.")
            return redirect('mark_attendance', assignment_id=assignment.id)

    selected_date = request.GET.get('date') or now().date()
    existing_records = Attendance.objects.filter(
        class_assigned=assignment.class_assigned,
        academic_year=assignment.academic_year,
        date=selected_date
    )

    attendance_dict = {a.student_id: a for a in existing_records}

    is_edit_mode = existing_records.exists()
    return render(request, 'teachers/mark_attendance.html', {
        'assignment': assignment,
        'students': students,
        'selected_date': selected_date,
        'attendance_dict': attendance_dict,
        'is_edit_mode': is_edit_mode,
    })

def teacher_grades(request):
    return render(request, 'teachers/grades.html')

def teacher_schedule(request):
    return render(request, 'teachers/schedule.html')