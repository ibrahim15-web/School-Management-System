from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

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
    student_grades     = [] 
    timetable          = {}
    DAYS               = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']  # ADD THIS
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
        enrollment        = None
        attendance_summary = None
        today_status      = None
        grades            = []
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
                # Attendance
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
                    'total':      total,
                    'present':    present,
                    'absent':     absent,
                    'percentage': pct,
                }
                # Today's status
                today_record = qs.filter(date=timezone.localdate()).first()
                if today_record:
                    today_status = today_record.status
                # Grades — now correctly inside the enrollment check
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
        children_data.append({
            'student':            student,
            'enrollment':         enrollment,
            'attendance_summary': attendance_summary,
            'today_status':       today_status,
            'grades':             grades,
        })
    announcements = Announcement.objects.filter(
        Q(target='all') | Q(target='parents')
    ).order_by('-is_pinned', '-created_at')[:4]
    recent_notifications = request.user.notifications.filter(
        is_read=False
    )[:5]
    return render(request, 'students/parent_dashboard.html', {
        'current_year':  current_year,
        'children_data': children_data,
        'announcements': announcements,
        'recent_notifications': recent_notifications,
    })

@login_required(login_url='login')
def student_report_card_pdf(request):
    """
    Generate and return a PDF report card for the logged-in student.
    Only students can access their own report card.
    """
    if not request.user.is_student:
        messages.error(request, 'Access denied.')
        return redirect('home')
    # ── Academic year ──
    try:
        current_year = AcademicYear.objects.get(is_current=True)
    except AcademicYear.DoesNotExist:
        messages.error(request, 'No active academic year found.')
        return redirect('student_dashboard')
    # ── Enrollment ──
    enrollment = (
        Enrollment.objects
        .filter(
            student=request.user,
            academic_year=current_year,
            status='active',
        )
        .select_related('class_assigned')
        .first()
    )
    if not enrollment:
        messages.error(request, 'You are not enrolled in any class this year.')
        return redirect('student_dashboard')
    # ── Grades ──
    grades = (
        Grade.objects
        .filter(
            student=request.user,
            class_assigned=enrollment.class_assigned,
            academic_year=current_year,
        )
        .select_related('subject', 'term')
        .order_by('subject__name', 'exam_type')
    )
    # ── Attendance ──
    attendance_qs = Attendance.objects.filter(
        student=request.user,
        class_assigned=enrollment.class_assigned,
        academic_year=current_year,
    )
    total_days   = attendance_qs.count()
    present_days = attendance_qs.filter(status=Attendance.STATUS_PRESENT).count()
    absent_days  = total_days - present_days
    attendance_pct = round((present_days / total_days) * 100, 1) if total_days > 0 else 0
    # ── Build PDF ──
    response = HttpResponse(content_type='application/pdf')
    student_name = request.user.get_full_name() or request.user.username
    filename = f"report_card_{request.user.username}_{current_year.name}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    # Custom styles
    style_title = ParagraphStyle(
        'ReportTitle',
        parent=styles['Title'],
        fontSize=20,
        textColor=colors.HexColor('#1f67f2'),
        spaceAfter=4,
        alignment=TA_CENTER,
    )
    style_subtitle = ParagraphStyle(
        'ReportSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#6b7280'),
        spaceAfter=2,
        alignment=TA_CENTER,
    )
    style_section = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=11,
        textColor=colors.HexColor('#111827'),
        spaceBefore=16,
        spaceAfter=6,
        borderPad=4,
    )
    style_normal = ParagraphStyle(
        'ReportNormal',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#374151'),
    )
    story = []
    # ── Header ──
    story.append(Paragraph('EduManager', style_title))
    story.append(Paragraph('School Management System', style_subtitle))
    story.append(Paragraph('Student Report Card', style_subtitle))
    story.append(Spacer(1, 0.3 * cm))
    story.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#1f67f2')))
    story.append(Spacer(1, 0.4 * cm))
    # ── Student Info Table ──
    story.append(Paragraph('Student Information', style_section))
    info_data = [
        ['Full Name',      student_name,                           'Academic Year', current_year.name],
        ['Username',       request.user.username,                  'Class',         enrollment.class_assigned.name],
        ['Email',          request.user.email,                     'Status',        enrollment.get_status_display()],
    ]
    info_table = Table(info_data, colWidths=[3.5 * cm, 6 * cm, 3.5 * cm, 4 * cm])
    info_table.setStyle(TableStyle([
        ('FONTNAME',    (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE',    (0, 0), (-1, -1), 9),
        ('FONTNAME',    (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME',    (2, 0), (2, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR',   (0, 0), (0, -1), colors.HexColor('#6b7280')),
        ('TEXTCOLOR',   (2, 0), (2, -1), colors.HexColor('#6b7280')),
        ('TEXTCOLOR',   (1, 0), (1, -1), colors.HexColor('#111827')),
        ('TEXTCOLOR',   (3, 0), (3, -1), colors.HexColor('#111827')),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.HexColor('#f9fafb'), colors.white]),
        ('GRID',        (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('PADDING',     (0, 0), (-1, -1), 6),
        ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(info_table)
    # ── Grades Table ──
    story.append(Paragraph('Academic Grades', style_section))
    if grades:
        grade_header = ['Subject', 'Type', 'Term', 'Score', 'Max', 'Percentage', 'Grade']
        grade_rows   = [grade_header]
        for g in grades:
            grade_rows.append([
                g.subject.name,
                g.get_exam_type_display(),
                g.term.name if g.term else '—',
                str(g.score),
                str(g.max_score),
                f'{g.percentage}%',
                g.letter_grade,
            ])
        # Color the letter grade column
        grade_table = Table(
            grade_rows,
            colWidths=[4.5 * cm, 3 * cm, 3 * cm, 2 * cm, 2 * cm, 2.5 * cm, 2 * cm],
        )
        grade_style = TableStyle([
            # Header row
            ('BACKGROUND',  (0, 0), (-1, 0), colors.HexColor('#1f67f2')),
            ('TEXTCOLOR',   (0, 0), (-1, 0), colors.white),
            ('FONTNAME',    (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',    (0, 0), (-1, 0), 9),
            ('ALIGN',       (0, 0), (-1, 0), 'CENTER'),
            # Data rows
            ('FONTNAME',    (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE',    (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
            ('ALIGN',       (3, 1), (-1, -1), 'CENTER'),
            ('GRID',        (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ('PADDING',     (0, 0), (-1, -1), 6),
            ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
        ])
        # Color each letter grade cell individually
        GRADE_COLORS = {
            'A': colors.HexColor('#dcfce7'),
            'B': colors.HexColor('#dbeafe'),
            'C': colors.HexColor('#fef9c3'),
            'D': colors.HexColor('#ffedd5'),
            'F': colors.HexColor('#fee2e2'),
        }
        for row_idx, g in enumerate(grades, start=1):
            bg = GRADE_COLORS.get(g.letter_grade, colors.white)
            grade_style.add('BACKGROUND', (6, row_idx), (6, row_idx), bg)
        grade_table.setStyle(grade_style)
        story.append(grade_table)
    else:
        story.append(Paragraph('No grades recorded for this academic year.', style_normal))
    # ── Attendance Summary ──
    story.append(Paragraph('Attendance Summary', style_section))
    att_data = [
        ['Total Days Recorded', 'Days Present', 'Days Absent', 'Attendance Rate'],
        [
            str(total_days),
            str(present_days),
            str(absent_days),
            f'{attendance_pct}%',
        ],
    ]
    att_table = Table(att_data, colWidths=[4.25 * cm] * 4)
    att_table.setStyle(TableStyle([
        ('BACKGROUND',  (0, 0), (-1, 0), colors.HexColor('#1f67f2')),
        ('TEXTCOLOR',   (0, 0), (-1, 0), colors.white),
        ('FONTNAME',    (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0), (-1, -1), 9),
        ('ALIGN',       (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME',    (0, 1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE',    (0, 1), (-1, 1), 14),
        ('TEXTCOLOR',   (1, 1), (1, 1), colors.HexColor('#16a34a')),
        ('TEXTCOLOR',   (2, 1), (2, 1), colors.HexColor('#dc2626')),
        ('GRID',        (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('PADDING',     (0, 0), (-1, -1), 10),
        ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(att_table)
    # ── Footer ──
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#e5e7eb')))
    story.append(Spacer(1, 0.2 * cm))
    generated_on = timezone.localtime(timezone.now()).strftime('%B %d, %Y at %H:%M')
    story.append(Paragraph(
        f'Generated on {generated_on} — EduManager School Management System',
        ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#9ca3af'),
            alignment=TA_CENTER,
        )
    ))
    doc.build(story)
    return response