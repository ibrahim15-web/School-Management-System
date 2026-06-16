"""
accounts/tests.py

Tests for the Accounts app — covering:
  - Authentication (login, logout, redirects)
  - process_pending_registrations API endpoint:
      method guard, permission guard, JSON validation,
      single approve, single reject, bulk actions,
      role assignment, idempotency, unknown user handling

Run with:
    python manage.py test accounts
"""

import json
from itertools import count as _count

from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser

_seq = _count(1)


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def make_user(username, role="none", approved=False):
    """
    Create a CustomUser.
    role: 'student' | 'teacher' | 'parent' | 'admin' | 'staff' | 'none'
    approved: if True, user is fully approved and active
    """
    seq = next(_seq)
    user = CustomUser.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="testpass123",
        phone_number=f"08{seq:09d}",
        national_id=f"12{seq:09d}",
    )
    if approved:
        user.is_active = True
        user.is_member_of_this_school = True
        user.status = "approved"
    else:
        # Pending state — default after registration
        user.is_active = False
        user.is_member_of_this_school = False
        user.status = "pending"

    if role == "student":
        user.is_student = True
    elif role == "teacher":
        user.is_teacher = True
    elif role == "parent":
        user.is_parent = True
    elif role == "admin":
        user.is_admin = True
    elif role == "staff":
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True

    user.save()
    return user


def post_json(client, url, payload):
    """Helper to POST JSON and return the response."""
    return client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json",
    )


# ─────────────────────────────────────────────────────────────
# 1. EXISTING AUTH TESTS (unchanged)
# ─────────────────────────────────────────────────────────────

class AuthTests(TestCase):

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="testpass123",
            phone_number="081200000000",
            national_id="1234567890",
        )
        self.user.is_active = True
        self.user.is_member_of_this_school = True
        self.user.status = "approved"
        self.user.save()

    def test_login_success(self):
        response = self.client.post(reverse("login"), {
            "email": "testuser@example.com",
            "password": "testpass123",
        })
        self.assertRedirects(response, reverse("home"))

    def test_login_wrong_password(self):
        response = self.client.post(reverse("login"), {
            "email": "testuser@example.com",
            "password": "wrongpassword",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/login.html")

    def test_login_nonexistent_email(self):
        response = self.client.post(reverse("login"), {
            "email": "nobody@example.com",
            "password": "testpass123",
        })
        self.assertRedirects(response, reverse("login"))

    def test_login_pending_user_is_blocked(self):
        pending_user = CustomUser.objects.create_user(
            username="pendinguser",
            email="pending@example.com",
            password="testpass123",
            phone_number="081200000001",
            national_id="9999999999",
        )
        pending_user.is_active = True
        pending_user.is_member_of_this_school = False
        pending_user.status = "pending"
        pending_user.save()

        response = self.client.post(reverse("login"), {
            "email": "pending@example.com",
            "password": "testpass123",
        })
        self.assertRedirects(response, reverse("login"))

    def test_login_rejected_user_is_blocked(self):
        rejected_user = CustomUser.objects.create_user(
            username="rejecteduser",
            email="rejected@example.com",
            password="testpass123",
            phone_number="081200000002",
            national_id="8888888888",
        )
        rejected_user.is_active = False
        rejected_user.is_member_of_this_school = False
        rejected_user.status = "rejected"
        rejected_user.save()

        response = self.client.post(reverse("login"), {
            "email": "rejected@example.com",
            "password": "testpass123",
        })
        self.assertRedirects(response, reverse("login"))

    def test_logout(self):
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("logout"))
        self.assertRedirects(response, reverse("login"))

    def test_authenticated_user_cannot_access_login_page(self):
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("login"))
        self.assertRedirects(response, reverse("home"))

    def test_authenticated_user_cannot_access_register_page(self):
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("register"))
        self.assertRedirects(response, reverse("home"))


# ─────────────────────────────────────────────────────────────
# 2. PROCESS PENDING REGISTRATIONS — METHOD AND AUTH GUARDS
# ─────────────────────────────────────────────────────────────

class ApprovalEndpointGuardTests(TestCase):
    """
    These tests confirm the endpoint rejects requests that
    should never reach the business logic at all.
    """

    def setUp(self):
        self.url = reverse("update_user_status")
        self.admin = make_user("guard_admin", role="staff")
        self.teacher = make_user("guard_teacher", role="teacher", approved=True)
        self.pending = make_user("guard_pending")

    def test_get_request_returns_405(self):
        """
        WHY: The endpoint is POST-only. A GET request (e.g. from
        someone typing the URL in a browser) must be rejected cleanly,
        not crash or accidentally process anything.
        """
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_unauthenticated_request_returns_403(self):
        """
        WHY: No session = no access. The endpoint must not process
        any payload from an unauthenticated caller.
        Django's @login_required redirects to login (302) rather
        than returning 403.
        """
        response = post_json(self.client, self.url, {
            "action": "approve",
            "users": [{"id": str(self.pending.id), "role": "student"}],
        })
        # @login_required redirects unauthenticated users to the login page
        self.assertEqual(response.status_code, 302)

    def test_non_staff_user_returns_403(self):
        """
        WHY: A teacher with a valid session must not be able to
        approve or reject other users. Only staff can do this.
        """
        self.client.force_login(self.teacher)
        response = post_json(self.client, self.url, {
            "action": "approve",
            "users": [{"id": str(self.pending.id), "role": "student"}],
        })
        self.assertEqual(response.status_code, 403)

    def test_malformed_json_returns_400(self):
        """
        WHY: The endpoint parses request.body as JSON. Sending
        garbage (e.g. a broken form post) must return 400, not 500.
        """
        self.client.force_login(self.admin)
        response = self.client.post(
            self.url,
            data="this is not json{{{",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_action_returns_400(self):
        self.client.force_login(self.admin)
        response = post_json(self.client, self.url, {
            "action": "delete",   # not a valid action
            "users": [{"id": str(self.pending.id), "role": "student"}],
        })
        self.assertEqual(response.status_code, 400)

    def test_empty_users_list_returns_400(self):
        self.client.force_login(self.admin)
        response = post_json(self.client, self.url, {
            "action": "approve",
            "users": [],
        })
        self.assertEqual(response.status_code, 400)

    def test_reject_without_reason_returns_400(self):
        """
        WHY: A rejection without a reason leaves the user with no
        explanation. The backend enforces this, not just the frontend.
        """
        self.client.force_login(self.admin)
        response = post_json(self.client, self.url, {
            "action": "reject",
            "users": [{"id": str(self.pending.id), "role": None}],
            # 'reason' is missing entirely
        })
        self.assertEqual(response.status_code, 400)

    def test_reject_with_blank_reason_returns_400(self):
        self.client.force_login(self.admin)
        response = post_json(self.client, self.url, {
            "action": "reject",
            "reason": "   ",   # whitespace only — should be treated as blank
            "users": [{"id": str(self.pending.id), "role": None}],
        })
        self.assertEqual(response.status_code, 400)

    def test_approve_without_role_returns_400(self):
        """
        WHY: Approving a user without a role would create an account
        with no role flags set — they could log in but see nothing.
        """
        self.client.force_login(self.admin)
        response = post_json(self.client, self.url, {
            "action": "approve",
            "users": [{"id": str(self.pending.id), "role": None}],
        })
        self.assertEqual(response.status_code, 400)


# ─────────────────────────────────────────────────────────────
# 3. SINGLE APPROVE — ROLE ASSIGNMENT
# ─────────────────────────────────────────────────────────────

class SingleApproveTests(TestCase):
    """
    Confirm that approving a user sets exactly the right fields
    and only the right role flag.
    """

    def setUp(self):
        self.url = reverse("update_user_status")
        self.admin = make_user("approve_admin", role="staff")

    def _approve(self, user, role):
        return post_json(self.client, self.url, {
            "action": "approve",
            "users": [{"id": str(user.id), "role": role}],
        })

    def test_approve_as_student_sets_correct_flags(self):
        pending = make_user("pending_student")
        self.client.force_login(self.admin)
        response = self._approve(pending, "student")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")

        pending.refresh_from_db()
        self.assertTrue(pending.is_student)
        self.assertTrue(pending.is_active)
        self.assertTrue(pending.is_member_of_this_school)
        self.assertEqual(pending.status, "approved")

    def test_approve_as_teacher_sets_correct_flags(self):
        pending = make_user("pending_teacher")
        self.client.force_login(self.admin)
        self._approve(pending, "teacher")

        pending.refresh_from_db()
        self.assertTrue(pending.is_teacher)
        self.assertFalse(pending.is_student)
        self.assertEqual(pending.status, "approved")

    def test_approve_as_parent_sets_correct_flags(self):
        pending = make_user("pending_parent")
        self.client.force_login(self.admin)
        self._approve(pending, "parent")

        pending.refresh_from_db()
        self.assertTrue(pending.is_parent)
        self.assertFalse(pending.is_student)
        self.assertFalse(pending.is_teacher)

    def test_approve_as_admin_sets_correct_flags(self):
        pending = make_user("pending_admin_r")
        self.client.force_login(self.admin)
        self._approve(pending, "admin")

        pending.refresh_from_db()
        self.assertTrue(pending.is_admin)
        self.assertFalse(pending.is_student)
        self.assertFalse(pending.is_teacher)

    def test_approve_clears_previous_rejection_reason(self):
        """
        WHY: A previously rejected user can be re-evaluated and approved.
        Their rejection_reason must be cleared so the profile is clean.
        """
        pending = make_user("prev_rejected")
        pending.status = "rejected"
        pending.rejection_reason = "Missing documents"
        pending.save()

        self.client.force_login(self.admin)
        self._approve(pending, "student")

        pending.refresh_from_db()
        self.assertEqual(pending.status, "approved")
        self.assertIsNone(pending.rejection_reason)

    def test_only_one_role_flag_is_set_after_approval(self):
        """
        WHY: A user who registered as a student but is being approved
        as a teacher must have their student flag cleared.
        No user should ever have two role flags set simultaneously.
        """
        pending = make_user("dual_role_risk")
        pending.is_student = True   # set during registration
        pending.save()

        self.client.force_login(self.admin)
        self._approve(pending, "teacher")

        pending.refresh_from_db()
        self.assertTrue(pending.is_teacher)
        self.assertFalse(pending.is_student)   # must be cleared


# ─────────────────────────────────────────────────────────────
# 4. SINGLE REJECT
# ─────────────────────────────────────────────────────────────

class SingleRejectTests(TestCase):

    def setUp(self):
        self.url = reverse("update_user_status")
        self.admin = make_user("reject_admin", role="staff")

    def _reject(self, user, reason="Incomplete application"):
        return post_json(self.client, self.url, {
            "action": "reject",
            "reason": reason,
            "users": [{"id": str(user.id), "role": None}],
        })

    def test_reject_sets_correct_flags(self):
        pending = make_user("pending_rej1")
        self.client.force_login(self.admin)
        response = self._reject(pending)

        self.assertEqual(response.status_code, 200)
        pending.refresh_from_db()
        self.assertEqual(pending.status, "rejected")
        self.assertFalse(pending.is_active)
        self.assertFalse(pending.is_member_of_this_school)

    def test_reject_stores_reason(self):
        """
        WHY: The rejection reason is shown to the user on their
        waiting page and in the admin user detail view.
        It must be stored exactly as provided.
        """
        pending = make_user("pending_rej2")
        self.client.force_login(self.admin)
        self._reject(pending, reason="National ID image was unclear")

        pending.refresh_from_db()
        self.assertEqual(pending.rejection_reason, "National ID image was unclear")

    def test_reject_clears_all_role_flags(self):
        """
        WHY: A rejected user must have no active role.
        If they somehow get reactivated later, an admin must
        explicitly assign a role — not inherit a stale one.
        """
        pending = make_user("pending_rej3")
        pending.is_student = True
        pending.save()

        self.client.force_login(self.admin)
        self._reject(pending)

        pending.refresh_from_db()
        self.assertFalse(pending.is_student)
        self.assertFalse(pending.is_teacher)
        self.assertFalse(pending.is_parent)
        self.assertFalse(pending.is_admin)


# ─────────────────────────────────────────────────────────────
# 5. BULK ACTIONS
# ─────────────────────────────────────────────────────────────

class BulkActionTests(TestCase):

    def setUp(self):
        self.url = reverse("update_user_status")
        self.admin = make_user("bulk_admin", role="staff")

    def test_bulk_approve_multiple_users(self):
        """
        WHY: The admin dashboard allows selecting all pending users
        and approving them in one click. All must be processed.
        """
        p1 = make_user("bulk_p1")
        p2 = make_user("bulk_p2")
        p3 = make_user("bulk_p3")

        self.client.force_login(self.admin)
        response = post_json(self.client, self.url, {
            "action": "approve",
            "users": [
                {"id": str(p1.id), "role": "student"},
                {"id": str(p2.id), "role": "teacher"},
                {"id": str(p3.id), "role": "parent"},
            ],
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 3)

        for user in [p1, p2, p3]:
            user.refresh_from_db()
            self.assertEqual(user.status, "approved")

    def test_bulk_reject_multiple_users(self):
        p1 = make_user("bulk_rj1")
        p2 = make_user("bulk_rj2")

        self.client.force_login(self.admin)
        response = post_json(self.client, self.url, {
            "action": "reject",
            "reason": "Documents not submitted",
            "users": [
                {"id": str(p1.id), "role": None},
                {"id": str(p2.id), "role": None},
            ],
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)

        for user in [p1, p2]:
            user.refresh_from_db()
            self.assertEqual(user.status, "rejected")
            self.assertEqual(user.rejection_reason, "Documents not submitted")

    def test_bulk_approve_with_mixed_roles(self):
        """
        WHY: Each user in a bulk approve can have a different role.
        The endpoint must apply the correct role to each user
        individually, not one role to all.
        """
        student_user = make_user("bulk_mix_s")
        teacher_user = make_user("bulk_mix_t")

        self.client.force_login(self.admin)
        post_json(self.client, self.url, {
            "action": "approve",
            "users": [
                {"id": str(student_user.id), "role": "student"},
                {"id": str(teacher_user.id), "role": "teacher"},
            ],
        })

        student_user.refresh_from_db()
        teacher_user.refresh_from_db()

        self.assertTrue(student_user.is_student)
        self.assertFalse(student_user.is_teacher)

        self.assertTrue(teacher_user.is_teacher)
        self.assertFalse(teacher_user.is_student)


# ─────────────────────────────────────────────────────────────
# 6. IDEMPOTENCY AND EDGE CASES
# ─────────────────────────────────────────────────────────────

class IdempotencyTests(TestCase):
    """
    The endpoint must behave safely when called multiple times
    or with unexpected data.
    """

    def setUp(self):
        self.url = reverse("update_user_status")
        self.admin = make_user("idem_admin", role="staff")

    def test_approving_already_approved_user_is_skipped(self):
        """
        WHY: Double-clicking approve in the UI or retrying a failed
        request must not corrupt the user's state or count them twice.
        """
        already_approved = make_user("already_ok", role="student", approved=True)

        self.client.force_login(self.admin)
        response = post_json(self.client, self.url, {
            "action": "approve",
            "users": [{"id": str(already_approved.id), "role": "teacher"}],
        })

        # Should succeed but count 0 — user was skipped
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)

        # Role must not have changed
        already_approved.refresh_from_db()
        self.assertTrue(already_approved.is_student)
        self.assertFalse(already_approved.is_teacher)

    def test_rejecting_already_rejected_user_is_skipped(self):
        rejected = make_user("already_rej")
        rejected.status = "rejected"
        rejected.save()

        self.client.force_login(self.admin)
        response = post_json(self.client, self.url, {
            "action": "reject",
            "reason": "Second rejection attempt",
            "users": [{"id": str(rejected.id), "role": None}],
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)

    def test_unknown_user_id_is_skipped_not_crashed(self):
        """
        WHY: A race condition can occur — the admin selects users,
        a second admin rejects them first, then the first admin
        submits their approval. The missing users must be skipped
        gracefully, not crash the entire batch.
        """
        import uuid
        fake_id = str(uuid.uuid4())

        valid_pending = make_user("valid_alongside")
        self.client.force_login(self.admin)
        response = post_json(self.client, self.url, {
            "action": "approve",
            "users": [
                {"id": fake_id, "role": "student"},          # unknown
                {"id": str(valid_pending.id), "role": "student"},  # valid
            ],
        })

        # Should succeed — valid user was processed, unknown was skipped
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)

        valid_pending.refresh_from_db()
        self.assertEqual(valid_pending.status, "approved")

    def test_response_count_reflects_only_processed_users(self):
        """
        WHY: The frontend uses the count in the success response to
        show 'X users approved'. If skipped users inflate the count,
        the UI shows a misleading number.
        """
        p1 = make_user("count_p1")
        p2 = make_user("count_p2", approved=True)  # already approved — will be skipped

        self.client.force_login(self.admin)
        response = post_json(self.client, self.url, {
            "action": "approve",
            "users": [
                {"id": str(p1.id), "role": "student"},
                {"id": str(p2.id), "role": "student"},
            ],
        })

        # Only p1 was actually processed
        self.assertEqual(response.json()["count"], 1)