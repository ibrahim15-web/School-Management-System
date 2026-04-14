# teachers/analytics.py
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
# Local import
from .models import Attendance

def get_last_7_days_attendance():
    """
    Returns attendance data for the last 7 calendar days
    where at least one record exists.

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
        .filter(date__gte=seven_days_ago, date__lte=today)
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

    Why separate from the 7-day query: this runs on every dashboard load,
    so it should be as tight as possible — one date, two counts.
    """
    today = timezone.localdate()

    result = (
        Attendance.objects
        .filter(date=today)
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
    Returns attendance data for teachers only (last 7 days).
    Same structure as student chart for reuse in frontend.
    """

    today = timezone.localdate()
    seven_days_ago = today - timedelta(days=6)

    records = (
        Attendance.objects
        .filter(
            date__gte=seven_days_ago,
            date__lte=today,
            student__is_teacher=True   # ✅ KEY FILTER
        )
        .values('date')
        .annotate(
            present_count=Count('id', filter=Q(status=Attendance.STATUS_PRESENT)),
            absent_count=Count('id', filter=Q(status=Attendance.STATUS_ABSENT)),
        )
        .order_by('date')
    )

    labels = []
    present_data = []
    absent_data = []

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
    qs = Attendance.objects.filter(student_id=student_id)

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
# teachers/analytics.py  (add below)
def get_filtered_attendance(
    class_id=None,
    student_id=None,
    date_from=None,
    date_to=None,
    academic_year=None,
):
    """
    Generic filtered attendance query used for reports and exports.

    All filters are optional and composable — only applied when provided.
    This is the single source of truth for any attendance filtering.
    """
    qs = Attendance.objects.select_related(
        'student',
        'class_assigned',
        'academic_year',
        'marked_by',
    )

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