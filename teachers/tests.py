"""
teachers/tests.py

Tests for the Teachers app — covering:
  - Teacher dashboard access and data correctness
  - Attendance marking (create and edit mode)
  - Grade entry (create and update)
  - Teacher attendance (admin-only)
  - Attendance report role scoping
  - Schedule, grades list, and student list access guards

Run with:
    python manage.py test teachers
"""

from datetime import date

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from itertools import count as _count
_seq = _count(1)

from accounts.models import CustomUser
from academics.models import (
    AcademicYear,
    Class,
    Subject,
    TeachingAssignment,
    Grade,
    TimetableSlot,
)
from students.models import Enrollment, ParentStudent
from teachers.models import Attendance, TeacherAttendance


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def make_year(name="2024-2025", is_current=True):
    return AcademicYear.objects.create(
        name=name,
        start_date=date(2024, 7, 1),
        end_date=date(2025, 6, 30),
        is_current=is_current,
    )


def make_subject(name="Mathematics", code="MTH01"):
    return Subject.objects.create(name=name, code=code)


def make_class(year, name="Grade 10-A", capacity=30):
    return Class.objects.create(name=name, academic_year=year, capacity=capacity)


def make_user(username, role, **kwargs):
    seq = next(_seq)
    user = CustomUser.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="testpass123",
        phone_number=f"08{seq:09d}",
        national_id=f"99{seq:09d}",
    )
    user.is_active = True
    user.is_member_of_this_school = True
    user.status = "approved"

    if role == "student":
        user.is_student = True
    elif role == "teacher":
        user.is_teacher = True
    elif role == "parent":
        user.is_parent = True
    elif role == "staff":
        user.is_staff = True
        user.is_superuser = True

    for attr, val in kwargs.items():
        setattr(user, attr, val)

    user.save()
    return user


def make_assignment(teacher, subject, cls, year):
    return TeachingAssignment.objects.create(
        teacher=teacher,
        subject=subject,
        class_assigned=cls,
        academic_year=year,
    )


def make_enrollment(student, cls, year):
    return Enrollment.objects.create(
        student=student,
        class_assigned=cls,
        academic_year=year,
        status="active",
    )


# ─────────────────────────────────────────────────────────────
# 1. TEACHER DASHBOARD
# ─────────────────────────────────────────────────────────────

class TeacherDashboardTests(TestCase):

    def setUp(self):
        self.teacher = make_user("teacher_dash", "teacher")
        self.student = make_user("student_dash", "student")
        self.admin = make_user("admin_dash", "staff")

    def test_unauthenticated_user_redirected(self):
        response = self.client.get(reverse("teacher_dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_non_teacher_is_denied(self):
        """
        WHY: Students visiting /teachers/teacher_dashboard/ must be
        blocked, not shown an empty teacher view.
        """
        self.client.force_login(self.student)
        response = self.client.get(reverse("teacher_dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_teacher_can_access_dashboard(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("teacher_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "teachers/teacher_dashboard.html")

    def test_dashboard_shows_correct_student_count(self):
        """
        WHY: A teacher with two subjects in the same class of 3 students
        should see 3 students — not 6 (double-counted).
        This tests the distinct() fix made earlier.
        """
        year = make_year()
        cls = make_class(year)
        subj1 = make_subject("Maths", "MTH01")
        subj2 = make_subject("Physics", "PHY01")
        cls.subjects.add(subj1, subj2)

        make_assignment(self.teacher, subj1, cls, year)
        make_assignment(self.teacher, subj2, cls, year)

        for i in range(3):
            s = make_user(f"ds_student{i}", "student")
            make_enrollment(s, cls, year)

        self.client.force_login(self.teacher)
        response = self.client.get(reverse("teacher_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_students"], 3)

    def test_dashboard_with_no_current_year(self):
        """
        WHY: If no academic year is set as current, the dashboard must
        still load — not crash with a DoesNotExist exception.
        """
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("teacher_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["current_year"])


# ─────────────────────────────────────────────────────────────
# 2. MARK ATTENDANCE
# ─────────────────────────────────────────────────────────────

class MarkAttendanceTests(TestCase):

    def setUp(self):
        self.year = make_year()
        self.subject = make_subject()
        self.cls = make_class(self.year)
        self.cls.subjects.add(self.subject)

        self.teacher = make_user("teacher_att", "teacher")
        self.other_teacher = make_user("other_teacher", "teacher")
        self.student = make_user("student_att", "student")

        self.assignment = make_assignment(self.teacher, self.subject, self.cls, self.year)
        make_enrollment(self.student, self.cls, self.year)

    def test_get_mark_attendance_page_loads(self):
        self.client.force_login(self.teacher)
        response = self.client.get(
            reverse("mark_attendance", args=[self.assignment.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "teachers/mark_attendance.html")

    def test_non_teacher_cannot_access_mark_attendance(self):
        student = make_user("block_student", "student")
        self.client.force_login(student)
        response = self.client.get(
            reverse("mark_attendance", args=[self.assignment.id])
        )
        self.assertEqual(response.status_code, 302)

    def test_teacher_cannot_access_another_teachers_assignment(self):
        """
        WHY: get_object_or_404 scopes the assignment to
        request.user.teaching_assignments — so a teacher trying to
        mark attendance for another teacher's class gets a 404,
        not someone else's student data.
        """
        self.client.force_login(self.other_teacher)
        response = self.client.get(
            reverse("mark_attendance", args=[self.assignment.id])
        )
        self.assertEqual(response.status_code, 404)

    def test_posting_attendance_creates_record(self):
        self.client.force_login(self.teacher)
        today = timezone.localdate().isoformat()
        response = self.client.post(
            reverse("mark_attendance", args=[self.assignment.id]),
            {
                "date": today,
                f"student_{self.student.id}": "present",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Attendance.objects.filter(
                student=self.student,
                class_assigned=self.cls,
                academic_year=self.year,
                date=today,
                status="present",
            ).exists()
        )

    def test_posting_attendance_marks_absent(self):
        self.client.force_login(self.teacher)
        today = timezone.localdate().isoformat()
        self.client.post(
            reverse("mark_attendance", args=[self.assignment.id]),
            {
                "date": today,
                f"student_{self.student.id}": "absent",
            },
        )
        record = Attendance.objects.get(
            student=self.student,
            class_assigned=self.cls,
            academic_year=self.year,
            date=today,
        )
        self.assertEqual(record.status, "absent")

    def test_resubmitting_attendance_updates_existing_record(self):
        """
        WHY: update_or_create must overwrite the old status, not
        create a second record. Duplicate attendance rows would
        corrupt the analytics.
        """
        today = timezone.localdate().isoformat()
        self.client.force_login(self.teacher)

        self.client.post(
            reverse("mark_attendance", args=[self.assignment.id]),
            {"date": today, f"student_{self.student.id}": "present"},
        )
        self.client.post(
            reverse("mark_attendance", args=[self.assignment.id]),
            {"date": today, f"student_{self.student.id}": "absent"},
        )

        records = Attendance.objects.filter(
            student=self.student,
            class_assigned=self.cls,
            academic_year=self.year,
            date=today,
        )
        self.assertEqual(records.count(), 1)
        self.assertEqual(records.first().status, "absent")

    def test_existing_attendance_loads_in_edit_mode(self):
        """
        WHY: When attendance already exists for a date, the template
        should be told it is in edit mode so the UI can warn the admin.
        """
        today = timezone.localdate()
        Attendance.objects.create(
            student=self.student,
            class_assigned=self.cls,
            academic_year=self.year,
            date=today,
            status="present",
            marked_by=self.teacher,
            updated_by=self.teacher,
        )
        self.client.force_login(self.teacher)
        response = self.client.get(
            reverse("mark_attendance", args=[self.assignment.id]),
            {"date": today.isoformat()},
        )
        self.assertTrue(response.context["is_edit_mode"])

    def test_attendance_without_date_redirects(self):
        """
        WHY: Submitting the form without selecting a date should not
        create a broken record — it should redirect back with an error.
        """
        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse("mark_attendance", args=[self.assignment.id]),
            {f"student_{self.student.id}": "present"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Attendance.objects.count(), 0)

    def test_attendance_sends_notification_to_student(self):
        """
        WHY: Notifications are a core feature. Marking attendance must
        create an in-app notification for the student.
        """
        self.client.force_login(self.teacher)
        today = timezone.localdate().isoformat()
        self.client.post(
            reverse("mark_attendance", args=[self.assignment.id]),
            {"date": today, f"student_{self.student.id}": "present"},
        )
        self.assertTrue(
            self.student.notifications.filter(notif_type="attendance").exists()
        )

    def test_attendance_sends_notification_to_parent(self):
        """
        WHY: Parents must also receive a notification when their child's
        attendance is recorded.
        """
        parent = make_user("parent_notif", "parent")
        ParentStudent.objects.create(parent=parent, student=self.student)

        self.client.force_login(self.teacher)
        today = timezone.localdate().isoformat()
        self.client.post(
            reverse("mark_attendance", args=[self.assignment.id]),
            {"date": today, f"student_{self.student.id}": "present"},
        )
        self.assertTrue(
            parent.notifications.filter(notif_type="attendance").exists()
        )


# ─────────────────────────────────────────────────────────────
# 3. ENTER GRADES
# ─────────────────────────────────────────────────────────────

class EnterGradesTests(TestCase):

    def setUp(self):
        self.year = make_year()
        self.subject = make_subject()
        self.cls = make_class(self.year)
        self.cls.subjects.add(self.subject)

        self.teacher = make_user("teacher_grade", "teacher")
        self.other_teacher = make_user("other_grade_t", "teacher")
        self.student = make_user("student_grade", "student")

        self.assignment = make_assignment(self.teacher, self.subject, self.cls, self.year)
        make_enrollment(self.student, self.cls, self.year)

    def test_grade_entry_page_loads(self):
        self.client.force_login(self.teacher)
        response = self.client.get(
            reverse("enter_grades", args=[self.assignment.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "teachers/enter_grades.html")

    def test_non_teacher_cannot_access_grade_entry(self):
        student = make_user("block_grade_s", "student")
        self.client.force_login(student)
        response = self.client.get(
            reverse("enter_grades", args=[self.assignment.id])
        )
        self.assertEqual(response.status_code, 302)

    def test_teacher_cannot_access_another_teachers_grade_entry(self):
        self.client.force_login(self.other_teacher)
        response = self.client.get(
            reverse("enter_grades", args=[self.assignment.id])
        )
        self.assertEqual(response.status_code, 404)

    def test_posting_grade_creates_record(self):
        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse("enter_grades", args=[self.assignment.id]),
            {
                "exam_type": "quiz",
                "term_id": "",
                "max_score": "100",
                f"score_{self.student.id}": "85",
                "save_grades": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Grade.objects.filter(
                student=self.student,
                subject=self.subject,
                class_assigned=self.cls,
                academic_year=self.year,
                exam_type="quiz",
                score=85,
            ).exists()
        )

    def test_posting_grade_updates_existing_record(self):
        """
        WHY: update_or_create must overwrite the old score rather than
        creating a duplicate. Two grades for the same exam type would
        break the report card.
        """
        self.client.force_login(self.teacher)
        base_post = {
            "exam_type": "midterm",
            "term_id": "",
            "max_score": "100",
            f"score_{self.student.id}": "70",
            "save_grades": "1",
        }
        self.client.post(reverse("enter_grades", args=[self.assignment.id]), base_post)

        base_post[f"score_{self.student.id}"] = "90"
        self.client.post(reverse("enter_grades", args=[self.assignment.id]), base_post)

        grades = Grade.objects.filter(
            student=self.student,
            subject=self.subject,
            exam_type="midterm",
        )
        self.assertEqual(grades.count(), 1)
        self.assertEqual(float(grades.first().score), 90.0)

    def test_blank_score_does_not_overwrite_existing(self):
        """
        WHY: Leaving a score field blank means 'skip this student',
        not 'set their score to zero'. The view skips blank inputs.
        """
        Grade.objects.create(
            student=self.student,
            subject=self.subject,
            class_assigned=self.cls,
            academic_year=self.year,
            exam_type="final",
            score=75,
            max_score=100,
            marked_by=self.teacher,
        )
        self.client.force_login(self.teacher)
        self.client.post(
            reverse("enter_grades", args=[self.assignment.id]),
            {
                "exam_type": "final",
                "term_id": "",
                "max_score": "100",
                f"score_{self.student.id}": "",
                "save_grades": "1",
            },
        )
        grade = Grade.objects.get(
            student=self.student, subject=self.subject, exam_type="final"
        )
        self.assertEqual(float(grade.score), 75.0)

    def test_grade_sends_notification_to_student(self):
        self.client.force_login(self.teacher)
        self.client.post(
            reverse("enter_grades", args=[self.assignment.id]),
            {
                "exam_type": "assignment",
                "term_id": "",
                "max_score": "100",
                f"score_{self.student.id}": "88",
                "save_grades": "1",
            },
        )
        self.assertTrue(
            self.student.notifications.filter(notif_type="grade").exists()
        )

    def test_grade_sends_notification_to_parent(self):
        parent = make_user("parent_grade_n", "parent")
        ParentStudent.objects.create(parent=parent, student=self.student)

        self.client.force_login(self.teacher)
        self.client.post(
            reverse("enter_grades", args=[self.assignment.id]),
            {
                "exam_type": "assignment",
                "term_id": "",
                "max_score": "100",
                f"score_{self.student.id}": "88",
                "save_grades": "1",
            },
        )
        self.assertTrue(
            parent.notifications.filter(notif_type="grade").exists()
        )

    def test_letter_grade_property_on_saved_grade(self):
        """
        WHY: The letter grade is a computed property used on dashboards
        and the PDF report card. Confirm the thresholds are correct.
        """
        grade = Grade.objects.create(
            student=self.student,
            subject=self.subject,
            class_assigned=self.cls,
            academic_year=self.year,
            exam_type="quiz",
            score=92,
            max_score=100,
            marked_by=self.teacher,
        )
        self.assertEqual(grade.letter_grade, "A")

        grade.score = 82
        grade.save()
        self.assertEqual(grade.letter_grade, "B")

        grade.score = 55
        grade.save()
        self.assertEqual(grade.letter_grade, "F")


# ─────────────────────────────────────────────────────────────
# 4. MARK TEACHER ATTENDANCE (admin only)
# ─────────────────────────────────────────────────────────────

class MarkTeacherAttendanceTests(TestCase):

    def setUp(self):
        self.admin = make_user("admin_ta", "staff")
        self.teacher = make_user("teacher_ta", "teacher")
        self.student = make_user("student_ta", "student")

    def test_unauthenticated_user_redirected(self):
        response = self.client.get(reverse("mark_teacher_attendance"))
        self.assertEqual(response.status_code, 302)

    def test_teacher_cannot_access_teacher_attendance_page(self):
        """
        WHY: Marking teacher attendance is an admin-only action.
        A teacher should not be able to mark their own or a
        colleague's attendance.
        """
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("mark_teacher_attendance"))
        self.assertEqual(response.status_code, 302)

    def test_student_cannot_access_teacher_attendance_page(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("mark_teacher_attendance"))
        self.assertEqual(response.status_code, 302)

    def test_admin_can_access_teacher_attendance_page(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("mark_teacher_attendance"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "teachers/mark_teacher_attendance.html")

    def test_admin_can_mark_teacher_as_present(self):
        today = timezone.localdate().isoformat()
        self.client.force_login(self.admin)
        self.client.post(
            reverse("mark_teacher_attendance"),
            {
                "date": today,
                f"teacher_{self.teacher.id}": "present",
            },
        )
        self.assertTrue(
            TeacherAttendance.objects.filter(
                teacher=self.teacher,
                date=today,
                status="present",
            ).exists()
        )

    def test_resubmitting_teacher_attendance_updates_record(self):
        """
        WHY: update_or_create must not create a second record when
        the admin corrects a mistake.
        """
        today = timezone.localdate().isoformat()
        self.client.force_login(self.admin)

        self.client.post(
            reverse("mark_teacher_attendance"),
            {"date": today, f"teacher_{self.teacher.id}": "present"},
        )
        self.client.post(
            reverse("mark_teacher_attendance"),
            {"date": today, f"teacher_{self.teacher.id}": "absent"},
        )

        records = TeacherAttendance.objects.filter(
            teacher=self.teacher, date=today
        )
        self.assertEqual(records.count(), 1)
        self.assertEqual(records.first().status, "absent")


# ─────────────────────────────────────────────────────────────
# 5. ATTENDANCE REPORT — ROLE SCOPING
# ─────────────────────────────────────────────────────────────

class AttendanceReportTests(TestCase):

    def setUp(self):
        self.year = make_year()
        self.subject = make_subject()

        self.cls_a = make_class(self.year, name="Class A")
        self.cls_b = make_class(self.year, name="Class B")
        self.cls_a.subjects.add(self.subject)

        self.teacher = make_user("teacher_rep", "teacher")
        self.admin = make_user("admin_rep", "staff")
        self.student = make_user("student_rep", "student")

        make_assignment(self.teacher, self.subject, self.cls_a, self.year)

    def test_unauthenticated_user_redirected(self):
        response = self.client.get(reverse("attendance_report"))
        self.assertEqual(response.status_code, 302)

    def test_student_cannot_access_report(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("attendance_report"))
        self.assertEqual(response.status_code, 302)

    def test_teacher_can_access_report(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("attendance_report"))
        self.assertEqual(response.status_code, 200)

    def test_admin_can_access_report(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("attendance_report"))
        self.assertEqual(response.status_code, 200)

    def test_teacher_only_sees_own_classes_in_filter(self):
        """
        WHY: A teacher assigned to Class A must not see Class B
        in their class dropdown. Data leakage between teachers
        is a privacy and trust issue.
        """
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("attendance_report"))
        class_ids = [c.id for c in response.context["classes"]]
        self.assertIn(self.cls_a.id, class_ids)
        self.assertNotIn(self.cls_b.id, class_ids)

    def test_admin_sees_all_classes_in_filter(self):
        """
        WHY: Admin needs full visibility. If the admin filter is
        accidentally scoped like a teacher's, they lose oversight.
        """
        self.client.force_login(self.admin)
        response = self.client.get(reverse("attendance_report"))
        class_ids = [c.id for c in response.context["classes"]]
        self.assertIn(self.cls_a.id, class_ids)
        self.assertIn(self.cls_b.id, class_ids)

    def test_no_filters_shows_no_records(self):
        """
        WHY: The page must not load all records by default.
        That would be a performance problem for large schools.
        """
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("attendance_report"))
        self.assertIsNone(response.context["page_obj"])

    def test_filter_returns_correct_records(self):
        enrolled_student = make_user("enrolled_rep", "student")
        make_enrollment(enrolled_student, self.cls_a, self.year)

        today = timezone.localdate()
        Attendance.objects.create(
            student=enrolled_student,
            class_assigned=self.cls_a,
            academic_year=self.year,
            date=today,
            status="present",
            marked_by=self.teacher,
            updated_by=self.teacher,
        )

        self.client.force_login(self.teacher)
        response = self.client.get(
            reverse("attendance_report"),
            {
                "class_id": str(self.cls_a.id),
                "student_id": "",
                "date_from": "",
                "date_to": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context["page_obj"])
        self.assertEqual(response.context["page_obj"].paginator.count, 1)


# ─────────────────────────────────────────────────────────────
# 6. REMAINING VIEW ACCESS GUARDS
# ─────────────────────────────────────────────────────────────

class TeacherViewAccessTests(TestCase):

    def setUp(self):
        self.teacher = make_user("teacher_access", "teacher")
        self.student = make_user("student_access", "student")

    def test_teacher_grades_list_requires_teacher(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("teacher_grades"))
        self.assertEqual(response.status_code, 302)

    def test_teacher_grades_list_loads_for_teacher(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("teacher_grades"))
        self.assertEqual(response.status_code, 200)

    def test_teacher_all_students_requires_teacher(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("teacher_all_students"))
        self.assertEqual(response.status_code, 302)

    def test_teacher_all_students_loads_for_teacher(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("teacher_all_students"))
        self.assertEqual(response.status_code, 200)

    def test_teacher_schedule_requires_teacher(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("teacher_schedule"))
        self.assertEqual(response.status_code, 302)

    def test_teacher_schedule_loads_for_teacher(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("teacher_schedule"))
        self.assertEqual(response.status_code, 200)

    def test_attendance_page_requires_teacher(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("teacher_attendance"))
        self.assertEqual(response.status_code, 302)

    def test_attendance_page_loads_for_teacher(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("teacher_attendance"))
        self.assertEqual(response.status_code, 200)