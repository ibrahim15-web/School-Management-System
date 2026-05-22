from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.timezone import now
from django.db.models import Q
from django.core.paginator import Paginator

from .models import *
from academics.models import *
from accounts.models import CustomUser
from teachers.analytics import get_filtered_attendance
from students.models import Enrollment, ParentStudent
from core.models import Announcement, Notification


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
    announcements = Announcement.objects.filter(
        Q(target='all') | Q(target='teachers')
    ).order_by('-is_pinned', '-created_at')[:4]
    recent_notifications = request.user.notifications.filter(
    is_read=False)[:5]
    context = {
        'teacher': request.user,
        'current_year': current_year,
        'assignments': assignments,
        'total_classes': total_classes,
        'total_subjects': total_subjects,
        'total_students': total_students,
        'total_assignments': total_assignments,
        'announcements': announcements,
        'recent_notifications': recent_notifications,
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

                Notification.send(
                    recipient=student,
                    title="Attendance recorded",
                    body=(
                        f"Your attendance for "
                        f"{assignment.class_assigned.name} on {date} "
                        f"was marked as {status}."
                    ),
                    notif_type='attendance',
                )
                # Notify parents too
                for link in ParentStudent.objects.filter(student=student).select_related('parent'):
                    Notification.send(
                        recipient=link.parent,
                        title="Child attendance recorded",
                        body=(
                            f"{student.get_full_name() or student.username} "
                            f"was marked {status} on {date} "
                            f"in {assignment.class_assigned.name}."
                        ),
                        notif_type='attendance',
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

@login_required(login_url='login')
def teacher_grades(request):
    """List all assignments — teacher picks one to enter grades for."""
    if not request.user.is_teacher:
        messages.error(request, 'Access denied.')
        return redirect('home')
    try:
        current_year = AcademicYear.objects.get(is_current=True)
    except AcademicYear.DoesNotExist:
        current_year = None
    assignments = (
        request.user.teaching_assignments
        .filter(academic_year=current_year)
        .select_related('subject', 'class_assigned')
        .order_by('class_assigned__name', 'subject__name')
    ) if current_year else []
    return render(request, 'teachers/grades.html', {
        'assignments': assignments,
        'current_year': current_year,
    })

@login_required(login_url='login')
def enter_grades(request, assignment_id):
    """Enter or update grades for all students in one class/subject."""
    if not request.user.is_teacher:
        messages.error(request, 'Access denied.')
        return redirect('home')

    assignment = get_object_or_404(
        request.user.teaching_assignments.select_related(
            'class_assigned', 'subject', 'academic_year'
        ),
        id=assignment_id,
    )
    students = CustomUser.objects.filter(
        enrollments__class_assigned=assignment.class_assigned,
        enrollments__academic_year=assignment.academic_year,
        enrollments__status='active',
    ).distinct().order_by('username')
    terms = Term.objects.filter(
        academic_year=assignment.academic_year
    ).order_by('start_date')
    # Selected exam type and term from GET/POST
    exam_type    = request.POST.get('exam_type') or request.GET.get('exam_type', 'quiz')
    selected_term_id = request.POST.get('term_id') or request.GET.get('term_id', '')
    selected_term = None
    if selected_term_id:
        try:
            selected_term = terms.get(id=selected_term_id)
        except Term.DoesNotExist:
            pass
    # Load existing grades for this combo so we can pre-fill
    existing_qs = Grade.objects.filter(
        subject=assignment.subject,
        class_assigned=assignment.class_assigned,
        academic_year=assignment.academic_year,
        exam_type=exam_type,
        term=selected_term,
    )
    existing_map = {g.student_id: g for g in existing_qs}
    if request.method == 'POST' and 'save_grades' in request.POST:
        max_score = request.POST.get('max_score', '100')
        try:
            max_score = float(max_score)
            if max_score <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, 'Max score must be a positive number.')
            max_score = 100
        saved = 0
        for student in students:
            raw = request.POST.get(f'score_{student.id}', '').strip()
            if raw == '':
                continue   # skip blank — don't overwrite existing
            try:
                score = float(raw)
                if score < 0 or score > max_score:
                    messages.warning(
                        request,
                        f'{student.username}: score {score} out of range, skipped.'
                    )
                    continue
            except ValueError:
                continue
            Grade.objects.update_or_create(
                student=student,
                subject=assignment.subject,
                class_assigned=assignment.class_assigned,
                academic_year=assignment.academic_year,
                exam_type=exam_type,
                term=selected_term,
                defaults={
                    'score':     score,
                    'max_score': max_score,
                    'marked_by': request.user,
                },
            )
            # Notify student
            Notification.send(
                recipient=student,
                title="Grade recorded",
                body=(
                    f"Your "
                    f"{dict(Grade.EXAM_TYPE_CHOICES).get(exam_type, exam_type)} "
                    f"score for {assignment.subject.name} "
                    f"has been recorded: {score}/{max_score}."
                ),
                notif_type='grade',
            )

            # Notify parents
            for link in ParentStudent.objects.filter(
                student=student
            ).select_related('parent'):
                Notification.send(
                    recipient=link.parent,
                    title="Child grade recorded",
                    body=(
                        f"{student.get_full_name() or student.username} "
                        f"received {score}/{max_score} "
                        f"in {assignment.subject.name} "
                        f"({dict(Grade.EXAM_TYPE_CHOICES).get(exam_type, exam_type)})."
                    ),
                    notif_type='grade',
                )
            saved += 1
        messages.success(request, f'Saved {saved} grade(s).')
        return redirect(
            f"{request.path}?exam_type={exam_type}"
            + (f"&term_id={selected_term_id}" if selected_term_id else "")
        )
    EXAM_TYPES = Grade.EXAM_TYPE_CHOICES
    return render(request, 'teachers/enter_grades.html', {
        'assignment':      assignment,
        'students':        students,
        'terms':           terms,
        'exam_types':      EXAM_TYPES,
        'exam_type':       exam_type,
        'selected_term':   selected_term,
        'selected_term_id': selected_term_id,
        'existing_map':    existing_map,
    })

@login_required(login_url='login')
def teacher_schedule(request):
    if not request.user.is_teacher:
        messages.error(request, 'Access denied.')
        return redirect('home')
    try:
        current_year = AcademicYear.objects.get(is_current=True)
    except AcademicYear.DoesNotExist:
        current_year = None
    slots = []
    if current_year:
        slots = (
            TimetableSlot.objects
            .filter(
                teacher=request.user,
                academic_year=current_year,
            )
            .select_related('subject', 'class_assigned')
            .order_by('day', 'start_time')
        )

    # Group by day so the template can render a clean schedule
    DAYS = ['monday','tuesday','wednesday','thursday','friday','saturday']
    schedule = {day: [] for day in DAYS}
    for slot in slots:
        schedule[slot.day].append(slot)

    return render(request, 'teachers/schedule.html', {
        'current_year': current_year,
        'schedule':     schedule,
        'days':         DAYS,
        'total_slots':  len(slots),
    })

@login_required(login_url='login')
def attendance_report(request):
    """
    Attendance report accessible by teachers and admins.
    Teachers see only their assigned classes.
    Admins see all classes for the current year.
    """
    if not (request.user.is_teacher or request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Access denied.')
        return redirect('home')
    try:
        current_year = AcademicYear.objects.get(is_current=True)
    except AcademicYear.DoesNotExist:
        current_year = None

    # Build class list based on role
    if request.user.is_staff or request.user.is_superuser:
        classes = (
            Class.objects.filter(academic_year=current_year).order_by('name')
            if current_year else []
        )
    else:
        assigned_class_ids = (
            request.user.teaching_assignments
            .filter(academic_year=current_year)
            .values('class_assigned')
            if current_year else []
        )
        classes = Class.objects.filter(
            id__in=assigned_class_ids
        ).order_by('name')
    # Read GET filters
    class_id   = request.GET.get('class_id',   '').strip()
    student_id = request.GET.get('student_id', '').strip()
    date_from  = request.GET.get('date_from',  '').strip()
    date_to    = request.GET.get('date_to',    '').strip()
    # Student dropdown — only populated when a class is selected
    students = []
    if class_id and current_year:
        students = (
            CustomUser.objects
            .filter(
                enrollments__class_assigned_id=class_id,
                enrollments__academic_year=current_year,
                enrollments__status='active',
            )
            .distinct()
            .order_by('username')
        )
    page_obj = None
    summary = None
    # Only query when at least one filter is active
    if class_id or student_id or date_from or date_to: 
        qs = get_filtered_attendance(
            class_id=class_id   or None,
            student_id=student_id or None,
            date_from=date_from  or None,
            date_to=date_to      or None,
            academic_year=current_year,
        )
        # Teachers must not see records outside their assigned classes
        if request.user.is_teacher and not request.user.is_staff:
            teacher_class_ids = (
                request.user.teaching_assignments
                .filter(academic_year=current_year)
                .values_list('class_assigned', flat=True)
            )
            qs = qs.filter(class_assigned__in=teacher_class_ids)
        total   = qs.count()
        present = qs.filter(status=Attendance.STATUS_PRESENT).count()
        absent  = total - present
        pct     = round((present / total) * 100, 1) if total > 0 else 0
        summary = {
            'total':      total,
            'present':    present,
            'absent':     absent,
            'percentage': pct,
        }
        paginator = Paginator(qs, 50)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
    
    return render(request, 'teachers/attendance_report.html', {
        'current_year':       current_year,
        'classes':            classes,
        'students':           students,
        'page_obj':           page_obj,
        'summary':            summary,
        'selected_class_id':  class_id,
        'selected_student_id':student_id,
        'date_from':          date_from,
        'date_to':            date_to,
    })