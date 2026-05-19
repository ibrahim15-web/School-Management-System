from django.test import TestCase
from django.urls import reverse
from accounts.models import CustomUser


class AuthTests(TestCase):

    def setUp(self):
        """
        Create a fully approved and active CustomUser for testing.
        We must set is_member_of_this_school=True and status='approved'
        otherwise the login view will reject the user before authentication.
        """
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='testpass123',
            phone_number='081200000000',
            national_id='1234567890',
        )
        self.user.is_active               = True
        self.user.is_member_of_this_school = True
        self.user.status                  = 'approved'
        self.user.save()

    def test_login_success(self):
        """
        A fully approved user logging in with correct credentials
        should be redirected to the home page.
        """
        response = self.client.post(reverse('login'), {
            'email':    'testuser@example.com',
            'password': 'testpass123',
        })
        self.assertRedirects(response, reverse('home'))

    def test_login_wrong_password(self):
        """
        A user logging in with the wrong password should be
        shown the login page again with a 200 response,
        not redirected — the form re-renders with an error message.
        """
        response = self.client.post(reverse('login'), {
            'email':    'testuser@example.com',
            'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/login.html')

    def test_login_nonexistent_email(self):
        """
        Logging in with an email that does not exist in the system
        should redirect back to login, not raise a 500 error.
        """
        response = self.client.post(reverse('login'), {
            'email':    'nobody@example.com',
            'password': 'testpass123',
        })
        self.assertRedirects(response, reverse('login'))

    def test_login_pending_user_is_blocked(self):
        """
        A user whose account is not yet approved (is_member_of_this_school=False)
        should not be able to log in even with correct credentials.
        """
        pending_user = CustomUser.objects.create_user(
            username='pendinguser',
            email='pending@example.com',
            password='testpass123',
            phone_number='081200000001',
            national_id='9999999999',
        )
        pending_user.is_active                = True
        pending_user.is_member_of_this_school = False
        pending_user.status                   = 'pending'
        pending_user.save()

        response = self.client.post(reverse('login'), {
            'email':    'pending@example.com',
            'password': 'testpass123',
        })
        self.assertRedirects(response, reverse('login'))

    def test_login_rejected_user_is_blocked(self):
        """
        A rejected user should be blocked at login
        and redirected back to the login page.
        """
        rejected_user = CustomUser.objects.create_user(
            username='rejecteduser',
            email='rejected@example.com',
            password='testpass123',
            phone_number='081200000002',
            national_id='8888888888',
        )
        rejected_user.is_active                = False
        rejected_user.is_member_of_this_school = False
        rejected_user.status                   = 'rejected'
        rejected_user.save()

        response = self.client.post(reverse('login'), {
            'email':    'rejected@example.com',
            'password': 'testpass123',
        })
        self.assertRedirects(response, reverse('login'))

    def test_logout(self):
        """
        A logged-in user hitting the logout URL should be
        redirected to the login page and their session cleared.
        """
        self.client.login(
            username='testuser',
            password='testpass123',
        )
        response = self.client.get(reverse('logout'))
        self.assertRedirects(response, reverse('login'))

    def test_authenticated_user_cannot_access_login_page(self):
        """
        An already logged-in user visiting the login page
        should be redirected to home immediately.
        """
        self.client.login(
            username='testuser',
            password='testpass123',
        )
        response = self.client.get(reverse('login'))
        self.assertRedirects(response, reverse('home'))

    def test_authenticated_user_cannot_access_register_page(self):
        """
        An already logged-in user visiting the register page
        should be redirected to home immediately.
        """
        self.client.login(
            username='testuser',
            password='testpass123',
        )
        response = self.client.get(reverse('register'))
        self.assertRedirects(response, reverse('home'))
