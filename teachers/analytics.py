# teachers/analytics.py
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
# Local import
from .models import Attendance, TeacherAttendance
from accounts.models import CustomUser

def get_last_7_days_attendance():
    """
    Returns attendance data for the last 7 calendar days
    where at least one record exists.

    Only counts records where student__is_student=True.
    This guards against any data inconsistency in the Attendance table.

    Why: Charts should only show school days with actual data.
    Showing empty weekends misleads admins.

    Returns a dict ready for Chart.js:
    {
        'labels': ['Mon Apr 07', 'Tue Apr 08', ...],
        'present': [24, 30, ...],
        'absent': [3, 2, ...],
        'dates': ['2026-04-07', ...]   # for linking to detail views
    }
    """
    today = timezone.localdate()
    seven_days_ago = today - timedelta(days=6)  # inclusive of today = 7 days

    # Single query: group by date, count present and absent
    records = (
        Attendance.objects
        .filter(date__gte=seven_days_ago, date__lte=today, student__is_student=True,)   # Explicit: students only
        .values('date')
        .annotate(
            present_count=Count('id', filter=Q(status=Attendance.STATUS_PRESENT)),
            absent_count=Count('id', filter=Q(status=Attendance.STATUS_ABSENT)),
        )
        .order_by('date')
    )

    # Format for Chart.js
    labels = []
    present_data = []
    absent_data = []
    dates = []

    for record in records:
        labels.append(record['date'].strftime('%a %b %d'))   # "Mon Apr 07"
        present_data.append(record['present_count'])
        absent_data.append(record['absent_count'])
        dates.append(record['date'].strftime('%Y-%m-%d'))

    return {
        'labels': labels,
        'present': present_data,
        'absent': absent_data,
        'dates': dates,
    }

def get_today_attendance_summary():
    """
    Returns today's school-wide attendance summary.

    Explicitly filters student__is_student=True so teacher or admin
    records never bleed into the student summary.

    Why separate from the 7-day query: this runs on every dashboard load,
    so it should be as tight as possible — one date, two counts.
    """
    today = timezone.localdate()

    result = (
        Attendance.objects
        .filter(date=today, student__is_student=True,) # Explicit: students only
        .aggregate(
            present=Count('id', filter=Q(status=Attendance.STATUS_PRESENT)),
            absent=Count('id', filter=Q(status=Attendance.STATUS_ABSENT)),
        )
    )

    present = result['present'] or 0
    absent = result['absent'] or 0
    total = present + absent
    percentage = round((present / total) * 100, 1) if total > 0 else 0

    return {
        'present': present,
        'absent': absent,
        'total': total,
        'percentage': percentage,
    }
def get_last_7_days_teacher_attendance():
    """
    Teacher attendance for the last 7 calendar days.
 
    Uses TeacherAttendance — a dedicated model separate from the student
    Attendance model. Returns the same dict structure so the frontend
    chart code in admin_dashboard.js does not need to change.
    """
    today = timezone.localdate()
    seven_days_ago = today - timedelta(days=6)
 
    records = (
        TeacherAttendance.objects
        .filter(
            date__gte=seven_days_ago,
            date__lte=today,
        )
        .values('date')
        .annotate(
            present_count=Count('id', filter=Q(status=TeacherAttendance.STATUS_PRESENT)),
            absent_count=Count('id', filter=Q(status=TeacherAttendance.STATUS_ABSENT)),
        )
        .order_by('date')
    )
 
    labels, present_data, absent_data = [], [], []
 
    for record in records:
        labels.append(record['date'].strftime('%a %b %d'))
        present_data.append(record['present_count'])
        absent_data.append(record['absent_count'])
 
    return {
        'labels': labels,
        'present': present_data,
        'absent': absent_data,
    }
def get_student_attendance_history(student_id, academic_year=None):
    """
    Returns full attendance history for a specific student.

    Why academic_year filter: a student's attendance in 2024
    is irrelevant when a teacher views their current year profile.
    Always scope to a year when possible.
    """
    qs = Attendance.objects.filter(student_id=student_id, student__is_student=True,)# Safety guard

    if academic_year:
        qs = qs.filter(academic_year=academic_year)

    records = qs.order_by('-date').values(
        'date',
        'status',
        'class_assigned__name',
    )

    total = qs.count()
    present = qs.filter(status=Attendance.STATUS_PRESENT).count()
    absent = total - present
    percentage = round((present / total) * 100, 1) if total > 0 else 0

    return {
        'records': list(records),
        'total': total,
        'present': present,
        'absent': absent,
        'percentage': percentage,
    }
def get_filtered_attendance(
    class_id=None,
    student_id=None,
    date_from=None,
    date_to=None,
    academic_year=None,
):
    """
    Generic filtered attendance query used for reports and exports.
    Always scoped to is_student=True so teacher data never leaks in.
    """
    qs = Attendance.objects.select_related(
        'student',
        'class_assigned',
        'academic_year',
        'marked_by',).filter(student__is_student=True)   # Baseline guard

    if class_id:
        qs = qs.filter(class_assigned_id=class_id)

    if student_id:
        qs = qs.filter(student_id=student_id)

    if academic_year:
        qs = qs.filter(academic_year=academic_year)

    if date_from:
        qs = qs.filter(date__gte=date_from)

    if date_to:
        qs = qs.filter(date__lte=date_to)

    return qs.order_by('-date')

def get_today_teacher_attendance_summary():
    today = timezone.localdate()

    # Query 1 — what has been recorded today
    result = (
        TeacherAttendance.objects
        .filter(date=today)
        .aggregate(
            present=Count('id', filter=Q(status=TeacherAttendance.STATUS_PRESENT)),
            absent=Count('id', filter=Q(status=TeacherAttendance.STATUS_ABSENT)),
        )
    )

    present = result['present'] or 0
    absent = result['absent'] or 0
    total_recorded = present + absent

    # Query 2 — total active teachers in the school
    # This is the real denominator. An unmarked teacher is not "present".
    total_teachers = CustomUser.objects.filter(
        is_teacher=True,
        is_member_of_this_school=True,
        is_active=True,
    ).count()
 
    not_marked = total_teachers - total_recorded

    # Percentage: present out of all teachers (not just those marked).
    # If no teachers exist yet, return 0 to avoid ZeroDivisionError.
    percentage = round((present / total_teachers) * 100, 1) if total_teachers > 0 else 0

    return {
        'present': present,
        'absent': absent,
        'total_recorded': total_recorded,
        'total_teachers': total_teachers,
        'not_marked': max(not_marked, 0),  # guard against negative if data is inconsistent
        'percentage': percentage,
    }