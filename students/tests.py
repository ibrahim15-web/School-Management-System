"""
students/tests.py

Tests for the Students app — covering:
  - Enrollment model business rules
  - ParentStudent linking
  - Student dashboard view access
  - Parent dashboard view access
  - Report card PDF access

Run with:
    python manage.py test students
"""

from django.test import TestCase
from django.urls import reverse
from django.core.exceptions import ValidationError
from itertools import count as _count
_seq = _count(1)

from accounts.models import CustomUser
from academics.models import AcademicYear, Class, Subject
from students.models import Enrollment, ParentStudent


# ─────────────────────────────────────────────────────────────
# HELPERS — build test objects without repeating boilerplate
# ─────────────────────────────────────────────────────────────

def make_year(name="2024-2025", is_current=True):
    """Create an AcademicYear.  Only one can be current, so callers
    should set is_current=False on extras."""
    from datetime import date
    year = AcademicYear.objects.create(
        name=name,
        start_date=date(2024, 7, 1),
        end_date=date(2025, 6, 30),
        is_current=is_current,
    )
    return year


def make_class(year, name="Grade 10-A", capacity=30):
    return Class.objects.create(
        name=name,
        academic_year=year,
        capacity=capacity,
    )


def make_approved_student(username="student1", **kwargs):
    seq = next(_seq)
    user = CustomUser.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="testpass123",
        phone_number=f"08{seq:09d}",
        national_id=f"12{seq:09d}",
    )
    user.is_student = True
    user.is_active = True
    user.is_member_of_this_school = True
    user.status = "approved"
    for attr, val in kwargs.items():
        setattr(user, attr, val)
    user.save()
    return user


def make_approved_teacher(username="teacher1"):
    seq = next(_seq)
    user = CustomUser.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="testpass123",
        phone_number=f"09{seq:09d}",
        national_id=f"99{seq:09d}",
    )
    user.is_teacher = True
    user.is_active = True
    user.is_member_of_this_school = True
    user.status = "approved"
    user.save()
    return user


def make_approved_parent(username="parent1"):
    seq = next(_seq)
    user = CustomUser.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="testpass123",
        phone_number=f"07{seq:09d}",
        national_id=f"88{seq:09d}",
    )
    user.is_parent = True
    user.is_active = True
    user.is_member_of_this_school = True
    user.status = "approved"
    user.save()
    return user


# ─────────────────────────────────────────────────────────────
# 1. ENROLLMENT — MODEL BUSINESS RULES
# ─────────────────────────────────────────────────────────────

class EnrollmentModelTests(TestCase):

    def setUp(self):
        self.year = make_year()
        self.cls = make_class(self.year, capacity=2)
        self.student = make_approved_student()

    def test_valid_enrollment_saves(self):
        """A fully approved student can be enrolled in a class."""
        enrollment = Enrollment(
            student=self.student,
            class_assigned=self.cls,
            academic_year=self.year,
            status="active",
        )
        enrollment.save()  # should not raise
        self.assertEqual(Enrollment.objects.count(), 1)

    def test_enrollment_str(self):
        enrollment = Enrollment.objects.create(
            student=self.student,
            class_assigned=self.cls,
            academic_year=self.year,
        )
        self.assertIn(self.student.username, str(enrollment))
        self.assertIn(self.cls.name, str(enrollment))

    def test_pending_student_cannot_enroll(self):
        """
        WHY: The approval workflow exists to ensure only verified students
        enter the school system.  Bypassing it at the model level would
        let data inconsistency sneak in silently.
        """
        pending = make_approved_student(username="pending99")
        pending.status = "pending"
        pending.is_member_of_this_school = False
        pending.save()

        enrollment = Enrollment(
            student=pending,
            class_assigned=self.cls,
            academic_year=self.year,
        )
        with self.assertRaises(ValidationError):
            enrollment.save()

    def test_not_member_of_school_cannot_enroll(self):
        """
        WHY: is_member_of_this_school is our custom approval flag.
        A user can be technically approved but still not a member
        (e.g. was revoked). The model must catch this.
        """
        student = make_approved_student(username="nonmember1")
        student.is_member_of_this_school = False
        student.save()

        enrollment = Enrollment(
            student=student,
            class_assigned=self.cls,
            academic_year=self.year,
        )
        with self.assertRaises(ValidationError):
            enrollment.save()

    def test_non_student_user_cannot_enroll(self):
        """
        WHY: Teachers or parents might be in CustomUser too.
        The model must enforce the is_student flag.
        """
        teacher = make_approved_teacher()
        enrollment = Enrollment(
            student=teacher,
            class_assigned=self.cls,
            academic_year=self.year,
        )
        with self.assertRaises(ValidationError):
            enrollment.save()

    def test_class_capacity_is_enforced(self):
        """
        WHY: Schools need hard capacity limits.  Without this a class
        of 30 could grow to 300 silently.
        """
        # Fill the class (capacity=2)
        s1 = make_approved_student(username="cap_s1")
        s2 = make_approved_student(username="cap_s2")
        Enrollment.objects.create(student=s1, class_assigned=self.cls, academic_year=self.year)
        Enrollment.objects.create(student=s2, class_assigned=self.cls, academic_year=self.year)

        # Third student should be blocked
        s3 = make_approved_student(username="cap_s3")
        enrollment = Enrollment(
            student=s3,
            class_assigned=self.cls,
            academic_year=self.year,
        )
        with self.assertRaises(ValidationError):
            enrollment.save()

    def test_one_enrollment_per_student_per_year(self):
        """
        WHY: unique_together guarantees one active enrollment per year.
        Trying to create a second one at the DB level should raise.
        """
        Enrollment.objects.create(
            student=self.student,
            class_assigned=self.cls,
            academic_year=self.year,
        )
        # Second enrollment in the same year (different class doesn't matter)
        cls2 = make_class(self.year, name="Grade 10-B", capacity=30)
        with self.assertRaises(Exception):
            # Django raises IntegrityError which becomes a db error
            Enrollment.objects.create(
                student=self.student,
                class_assigned=cls2,
                academic_year=self.year,
            )

    def test_wrong_academic_year_class_combination_rejected(self):
        """
        WHY: A class for 2023-2024 cannot be used in a 2024-2025 enrollment.
        This catches data integrity bugs at the model level.
        """
        from datetime import date
        other_year = AcademicYear.objects.create(
            name="2023-2024",
            start_date=date(2023, 7, 1),
            end_date=date(2024, 6, 30),
            is_current=False,
        )
        class_for_other_year = make_class(other_year, name="Old Grade 10", capacity=30)

        enrollment = Enrollment(
            student=self.student,
            class_assigned=class_for_other_year,
            academic_year=self.year,   # mismatch
        )
        with self.assertRaises(ValidationError):
            enrollment.save()

    def test_current_enrollment_property_counts_active_only(self):
        """
        WHY: The class capacity check uses current_enrollment.
        Withdrawn students must not count against capacity.
        """
        s1 = make_approved_student(username="prop_s1")
        enr = Enrollment.objects.create(
            student=s1,
            class_assigned=self.cls,
            academic_year=self.year,
            status="active",
        )
        self.assertEqual(self.cls.current_enrollment, 1)

        # Withdraw the student — should drop back to 0
        enr.status = "withdrawn"
        # bypass model save() to avoid full_clean re-checking capacity
        Enrollment.objects.filter(pk=enr.pk).update(status="withdrawn")
        # Force property re-evaluation by re-fetching
        self.cls.refresh_from_db()
        self.assertEqual(self.cls.current_enrollment, 0)

    def test_is_full_property(self):
        cls = make_class(self.year, name="Tiny Class", capacity=1)
        s = make_approved_student(username="full_test")
        Enrollment.objects.create(student=s, class_assigned=cls, academic_year=self.year)
        cls.refresh_from_db()
        self.assertTrue(cls.is_full)

    def test_subjects_property_returns_class_subjects(self):
        """
        Subjects flow from the class to the student via the enrollment.
        """
        subj = Subject.objects.create(name="Maths", code="MTH01")
        self.cls.subjects.add(subj)
        enrollment = Enrollment.objects.create(
            student=self.student,
            class_assigned=self.cls,
            academic_year=self.year,
        )
        self.assertIn(subj, enrollment.subjects)


# ─────────────────────────────────────────────────────────────
# 2. PARENT–STUDENT LINK
# ─────────────────────────────────────────────────────────────

class ParentStudentTests(TestCase):

    def setUp(self):
        self.parent = make_approved_parent()
        self.student = make_approved_student()

    def test_link_can_be_created(self):
        link = ParentStudent.objects.create(
            parent=self.parent,
            student=self.student,
        )
        self.assertEqual(link.parent, self.parent)
        self.assertEqual(link.student, self.student)

    def test_duplicate_link_is_rejected(self):
        """
        WHY: The same parent should not be linked to the same child twice.
        unique_together enforces this at the DB level.
        """
        ParentStudent.objects.create(parent=self.parent, student=self.student)
        with self.assertRaises(Exception):
            ParentStudent.objects.create(parent=self.parent, student=self.student)

    def test_one_parent_can_have_multiple_children(self):
        s2 = make_approved_student(username="child2")
        ParentStudent.objects.create(parent=self.parent, student=self.student)
        ParentStudent.objects.create(parent=self.parent, student=s2)
        self.assertEqual(
            ParentStudent.objects.filter(parent=self.parent).count(), 2
        )

    def test_one_student_can_have_multiple_parents(self):
        p2 = make_approved_parent(username="parent2")
        ParentStudent.objects.create(parent=self.parent, student=self.student)
        ParentStudent.objects.create(parent=p2, student=self.student)
        self.assertEqual(
            ParentStudent.objects.filter(student=self.student).count(), 2
        )

    def test_str_method(self):
        link = ParentStudent.objects.create(
            parent=self.parent, student=self.student
        )
        self.assertIn(self.parent.username, str(link))
        self.assertIn(self.student.username, str(link))


# ─────────────────────────────────────────────────────────────
# 3. STUDENT DASHBOARD VIEW — ACCESS CONTROL
# ─────────────────────────────────────────────────────────────

class StudentDashboardViewTests(TestCase):

    def setUp(self):
        self.student = make_approved_student()
        self.teacher = make_approved_teacher()
        self.parent = make_approved_parent()

    def test_unauthenticated_user_is_redirected_to_login(self):
        response = self.client.get(reverse("student_dashboard"))
        self.assertRedirects(response, "/accounts/login/?next=/students/dashboard/")

    def test_student_can_access_dashboard(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "students/student_dashboard.html")

    def test_teacher_is_denied_student_dashboard(self):
        """
        WHY: Role-based access must be strict.  A teacher visiting
        /students/dashboard/ should be blocked, not silently shown
        an empty student view.
        """
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("student_dashboard"))
        # Should redirect away (to home)
        self.assertEqual(response.status_code, 302)

    def test_parent_is_denied_student_dashboard(self):
        self.client.force_login(self.parent)
        response = self.client.get(reverse("student_dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_student_without_enrollment_sees_not_enrolled_message(self):
        """
        WHY: A student who has been approved but not yet placed
        in a class should see a helpful message, not an error.
        """
        # Make sure there IS a current year, but no enrollment
        make_year()
        self.client.force_login(self.student)
        response = self.client.get(reverse("student_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["enrollment"])

    def test_student_with_enrollment_sees_class_name(self):
        year = make_year()
        cls = make_class(year)
        Enrollment.objects.create(
            student=self.student,
            class_assigned=cls,
            academic_year=year,
        )
        self.client.force_login(self.student)
        response = self.client.get(reverse("student_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, cls.name)


# ─────────────────────────────────────────────────────────────
# 4. PARENT DASHBOARD VIEW — ACCESS CONTROL
# ─────────────────────────────────────────────────────────────

class ParentDashboardViewTests(TestCase):

    def setUp(self):
        self.parent = make_approved_parent()
        self.student = make_approved_student()
        self.teacher = make_approved_teacher()

    def test_unauthenticated_user_is_redirected(self):
        response = self.client.get(reverse("parent_dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_parent_can_access_dashboard(self):
        self.client.force_login(self.parent)
        response = self.client.get(reverse("parent_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "students/parent_dashboard.html")

    def test_student_is_denied_parent_dashboard(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("parent_dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_teacher_is_denied_parent_dashboard(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("parent_dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_parent_with_no_children_sees_empty_state(self):
        """
        WHY: A parent with no linked children should see the
        'no children linked' message, not a crash or empty table.
        """
        self.client.force_login(self.parent)
        response = self.client.get(reverse("parent_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["children_data"]), 0)

    def test_parent_sees_linked_child(self):
        ParentStudent.objects.create(parent=self.parent, student=self.student)
        self.client.force_login(self.parent)
        response = self.client.get(reverse("parent_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["children_data"]), 1)
        self.assertEqual(
            response.context["children_data"][0]["student"], self.student
        )


# ─────────────────────────────────────────────────────────────
# 5. REPORT CARD PDF VIEW — ACCESS CONTROL
# ─────────────────────────────────────────────────────────────

class ReportCardPDFViewTests(TestCase):

    def setUp(self):
        self.student = make_approved_student()
        self.teacher = make_approved_teacher()

    def test_unauthenticated_user_redirected(self):
        response = self.client.get(reverse("student_report_card_pdf"))
        self.assertEqual(response.status_code, 302)

    def test_non_student_is_denied(self):
        """
        WHY: Teachers or parents should never be able to download
        a student report card through this endpoint.
        """
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("student_report_card_pdf"))
        # Redirects away — does not serve a PDF
        self.assertEqual(response.status_code, 302)

    def test_student_without_enrollment_is_redirected(self):
        """
        WHY: Generating a PDF requires an active enrollment.
        Without one there is no meaningful data to put in the PDF.
        """
        make_year()
        self.client.force_login(self.student)
        response = self.client.get(reverse("student_report_card_pdf"))
        # Should redirect, not 200 or 500
        self.assertEqual(response.status_code, 302)

    def test_enrolled_student_receives_pdf(self):
        year = make_year()
        cls = make_class(year)
        Enrollment.objects.create(
            student=self.student,
            class_assigned=cls,
            academic_year=year,
        )
        self.client.force_login(self.student)
        response = self.client.get(reverse("student_report_card_pdf"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")