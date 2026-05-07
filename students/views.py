from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q

from academics.models import AcademicYear, TeachingAssignment, Grade, TimetableSlot
from students.models import Enrollment, ParentStudent
from teachers.models import Attendance
from core.models import Announcement


@login_required(login_url='login')
def student_dashboard(request):
    if not request.user.is_student:
        messages.error(request, 'Access denied. This page is for students only.')
        return redirect('home')
    # ── Academic year ──
    try:
        current_year = AcademicYear.objects.get(is_current=True)
    except AcademicYear.DoesNotExist:
        current_year = None
    # ── Enrollment ──
    enrollment = None
    if current_year:
        enrollment = (
            Enrollment.objects
            .filter(
                student=request.user,
                academic_year=current_year,
                status='active',
            )
            .select_related('class_assigned', 'academic_year')
            .first()
        )
    # ── Class-dependent data (only if enrolled) ───
    subjects          = []
    teachers          = []
    attendance_summary = None
    recent_attendance = []
    today_status      = None   # present | absent | None (not marked)
    if enrollment:
        assigned_class = enrollment.class_assigned
        # Subjects come directly from the class M2M
        subjects = assigned_class.subjects.select_related('department').all()
        # Teachers: who teaches what in this class this year
        teachers = (
            TeachingAssignment.objects
            .filter(
                class_assigned=assigned_class,
                academic_year=current_year,
            )
            .select_related('teacher', 'subject')
            .order_by('subject__name')
        )
        # Attendance queryset scoped to this student + class + year
        attendance_qs = Attendance.objects.filter(
            student=request.user,
            class_assigned=assigned_class,
            academic_year=current_year,
        )
        total   = attendance_qs.count()
        present = attendance_qs.filter(status=Attendance.STATUS_PRESENT).count()
        absent  = total - present
        percentage = round((present / total) * 100, 1) if total > 0 else 0
        attendance_summary = {
            'total':      total,
            'present':    present,
            'absent':     absent,
            'percentage': percentage,
        }
        # Last 10 records for the history table
        recent_attendance = attendance_qs.order_by('-date')[:10]
        student_grades = (
            Grade.objects
            .filter(
                student=request.user,
                class_assigned=assigned_class,
                academic_year=current_year,
            )
            .select_related('subject', 'term')
            .order_by('subject__name', 'exam_type')
        )
        DAYS = ['monday','tuesday','wednesday','thursday','friday','saturday']
        timetable_slots = (
            TimetableSlot.objects
            .filter(
                class_assigned=assigned_class,
                academic_year=current_year,
            )
            .select_related('subject', 'teacher')
            .order_by('day', 'start_time')
        )
        timetable = {day: [] for day in DAYS}
        for slot in timetable_slots:
            timetable[slot.day].append(slot)
        # Today's attendance status
        today = timezone.localdate()
        today_record = attendance_qs.filter(date=today).first()
        if today_record:
            today_status = today_record.status   # 'present' or 'absent'
    # Announcements visible to this student
    announcements = Announcement.objects.filter(
        Q(target='all') | Q(target='students')
    ).order_by('-is_pinned', '-created_at')[:4]
    recent_notifications = request.user.notifications.filter(
    is_read=False )[:5]
    context = {
        'current_year':      current_year,
        'enrollment':        enrollment,
        'subjects':          subjects,
        'teachers':          teachers,
        'attendance_summary': attendance_summary,
        'recent_attendance': recent_attendance,
        'student_grades': student_grades,
        'timetable': timetable,
        'days':      DAYS,
        'today_status':      today_status,
        'announcements': announcements,
        'recent_notifications': recent_notifications,
    }
    return render(request, 'students/student_dashboard.html', context)

@login_required(login_url='login')
def parent_dashboard(request):
    if not request.user.is_parent:
        messages.error(request, 'Access denied. This page is for parents only.')
        return redirect('home')
    try:
        current_year = AcademicYear.objects.get(is_current=True)
    except AcademicYear.DoesNotExist:
        current_year = None
    links = ParentStudent.objects.filter(
        parent=request.user
    ).select_related('student')
    children_data = []
    for link in links:
        student = link.student
        enrollment = None
        attendance_summary = None
        today_status = None
        grades = []
        if enrollment:
            grades = (
                Grade.objects
                .filter(
                    student=student,
                    class_assigned=enrollment.class_assigned,
                    academic_year=current_year,
                )
                .select_related('subject', 'term')
                .order_by('subject__name', 'exam_type')
            )
        if current_year:
            enrollment = (
                Enrollment.objects
                .filter(
                    student=student,
                    academic_year=current_year,
                    status='active',
                )
                .select_related('class_assigned')
                .first()
            )
            if enrollment:
                qs = Attendance.objects.filter(
                    student=student,
                    class_assigned=enrollment.class_assigned,
                    academic_year=current_year,
                )
                total   = qs.count()
                present = qs.filter(status=Attendance.STATUS_PRESENT).count()
                absent  = total - present
                pct     = round((present / total) * 100, 1) if total > 0 else 0
                attendance_summary = {
                    'total': total, 'present': present,
                    'absent': absent, 'percentage': pct,
                }
                today_record = qs.filter(date=timezone.localdate()).first()
                if today_record:
                    today_status = today_record.status
        announcements = Announcement.objects.filter(
            Q(target='all') | Q(target='parents')
        ).order_by('-is_pinned', '-created_at')[:4]
        recent_notifications = request.user.notifications.filter(
        is_read=False )[:5]
        children_data.append({
            'student':            student,
            'enrollment':         enrollment,
            'attendance_summary': attendance_summary,
            'today_status':       today_status,
            'grades':             grades,
        })
    return render(request, 'students/parent_dashboard.html', {
        'current_year':  current_year,
        'children_data': children_data,
        'announcements': announcements,
        'recent_notifications': recent_notifications,
    })