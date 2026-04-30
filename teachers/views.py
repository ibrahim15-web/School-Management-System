from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.timezone import now
from .models import *
from academics.models import *
from accounts.models import CustomUser
from students.models import Enrollment


@login_required(login_url='login')
def teacher_dashboard(request):
    """
    Teacher Dashboard
    Shows teacher's current teaching load:
    - Assignments
    - Classes
    - Students (DISTINCT — no double-counting across subjects)
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
    # FIX: Count DISTINCT students across all assigned classes.
    # The old approach summed assignment.student_count per assignment,
    # which double-counted students in classes with multiple subjects.
    # Example: Grade 10-A → Math (5) + Physics (5) = wrongly showed 10.
    # Now we query Enrollment directly, scoped to the teacher's classes,
    # and use .distinct() so each student is counted once regardless of
    # how many subjects they have with this teacher.
    if current_year:
        assigned_class_ids = assignments.values('class_assigned')
        total_students = (
            Enrollment.objects
            .filter(
                class_assigned__in=assigned_class_ids,
                academic_year=current_year,
                status='active',
            )
            .values('student')      # collapse to student PKs
            .distinct()             # one row per unique student
            .count()
        )
    else:
        total_students = 0
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
        request.user.teaching_assignments.select_related('class_assigned', 'subject'),
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

# TEACHER ATTENDANCE — Admin only
@login_required(login_url='login')
def mark_teacher_attendance(request):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'You do not have permission to access the admin dashboard.')
        return redirect('home')
    # Only teachers who are fully approved and active in the school
    teachers = CustomUser.objects.filter(
        is_teacher=True,
        is_member_of_this_school=True,
        is_active=True,
    ).order_by('username')

    if not teachers.exists():
        messages.warning(request, "No active teachers found.")
        return redirect('admin_dashboard')
    
    if request.method == 'POST':
        date = request.POST.get('date')
        if not date:
            messages.error(request, "Please select a date.")
            return redirect('mark_teacher_attendance')
        
        saved_count = 0
        error_count = 0

        for teacher in teachers:
            status = request.POST.get(f'teacher_{teacher.id}')

            if status not in [TeacherAttendance.STATUS_PRESENT, TeacherAttendance.STATUS_ABSENT]:
                error_count += 1
                continue
            TeacherAttendance.objects.update_or_create(
                teacher=teacher,
                date=date,
                defaults={
                    'status': status,
                    'marked_by': request.user,
                },
            )
            saved_count += 1

        if error_count:
            messages.warning(
                request,
                f"Saved {saved_count} record(s). {error_count} teacher(s) had missing data and were skipped."
            )
        else:
            messages.success(request, f"Attendance saved for {saved_count} teacher(s).")
        # Redirect back to same date so admin can confirm the saved state
        return redirect(f"{request.path}?date={date}")

    # GET — load existing records for the selected date (default: today)
    selected_date = request.GET.get('date') or now().date()

    existing_records = TeacherAttendance.objects.filter(date=selected_date)
    # Dict keyed by teacher PK → record; used in template to pre-fill radios
    attendance_dict = {record.teacher_id: record for record in existing_records}

    is_edit_mode = existing_records.exists()

    return render(request, 'teachers/mark_teacher_attendance.html', {
        'teachers': teachers,
        'selected_date': selected_date,
        'attendance_dict': attendance_dict,
        'is_edit_mode': is_edit_mode,
    })

def teacher_grades(request):
    return render(request, 'teachers/grades.html')

def teacher_schedule(request):
    return render(request, 'teachers/schedule.html')