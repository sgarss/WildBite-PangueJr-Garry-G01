"""Tests for the WildBite Account Feature.

Run with:  python manage.py test accounts
Django creates a temporary test database, runs every test inside it,
then deletes it. The real data in the `users` table is never touched.
"""
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

User = get_user_model()

PASSWORD = "Wildbite#2026x"


def make_student(email="student@cit.edu", full_name="Stu Dent"):
    return User.objects.create_user(email=email, password=PASSWORD, full_name=full_name)


def make_staff(email="staff@cit.edu", full_name="Canteen Staff"):
    return User.objects.create_user(
        email=email, password=PASSWORD, full_name=full_name, role=User.Role.STAFF
    )


# ---------------------------------------------------------------------------
# Model and manager
# ---------------------------------------------------------------------------

class UserModelTests(TestCase):
    def test_create_user_defaults_to_student_and_hashes_password(self):
        user = User.objects.create_user(email="Mixed.Case@CIT.edu", password=PASSWORD, full_name="A")
        self.assertEqual(user.email, "mixed.case@cit.edu")
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertFalse(user.is_staff)
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertTrue(user.is_student)
        self.assertFalse(user.is_canteen_staff)

    def test_create_superuser_is_staff_role(self):
        admin = User.objects.create_superuser(email="admin@cit.edu", password=PASSWORD, full_name="Admin")
        self.assertEqual(admin.role, User.Role.STAFF)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_database_check_constraint_rejects_unknown_role(self):
        """BR-02: the database itself only allows STUDENT or STAFF."""
        user = make_student()
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=user.pk).update(role="ADMIN")

    def test_database_rejects_duplicate_email(self):
        """BR-01: UNIQUE email at the database level."""
        make_student(email="dup@cit.edu")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(email="dup@cit.edu", password=PASSWORD, full_name="B")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class RegistrationTests(TestCase):
    url = reverse("accounts:register")

    def form_data(self, **overrides):
        data = {
            "full_name": "Juan Dela Cruz",
            "email": "Juan@CIT.edu",
            "password1": PASSWORD,
            "password2": PASSWORD,
        }
        data.update(overrides)
        return data

    def test_register_success_creates_student_with_hashed_password(self):
        response = self.client.post(self.url, self.form_data(), follow=True)

        self.assertRedirects(response, reverse("accounts:login"))
        self.assertContains(response, "Account created successfully. Please log in.")

        user = User.objects.get(email="juan@cit.edu")  # stored in lowercase
        self.assertEqual(user.full_name, "Juan Dela Cruz")
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))
        self.assertTrue(user.check_password(PASSWORD))

    def test_register_cannot_choose_staff_role(self):
        self.client.post(self.url, self.form_data(role="STAFF", is_staff="on", is_superuser="on"))
        user = User.objects.get(email="juan@cit.edu")
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_duplicate_email_rejected_even_with_different_case(self):
        make_student(email="juan@cit.edu")
        response = self.client.post(self.url, self.form_data(email="JUAN@Cit.Edu"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this email already exists.")
        self.assertEqual(User.objects.filter(email__iexact="juan@cit.edu").count(), 1)

    def test_password_mismatch(self):
        response = self.client.post(self.url, self.form_data(password2="Different#2026x"))
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "password2", "The two password fields didn’t match.")
        self.assertFalse(User.objects.exists())

    def test_required_fields_and_invalid_email(self):
        response = self.client.post(self.url, {"full_name": "   ", "email": "not-an-email"})
        form = response.context["form"]
        self.assertIn("full_name", form.errors)
        self.assertFormError(form, "email", "Enter a valid email address.")
        self.assertIn("password1", form.errors)
        self.assertIn("password2", form.errors)

    def test_weak_password_rejected(self):
        response = self.client.post(self.url, self.form_data(password1="12345", password2="12345"))
        self.assertIn("password2", response.context["form"].errors)
        self.assertFalse(User.objects.exists())

    def test_entered_values_kept_but_passwords_not_redisplayed(self):
        response = self.client.post(self.url, self.form_data(password2="Different#2026x"))
        self.assertContains(response, 'value="Juan Dela Cruz"')
        self.assertNotContains(response, PASSWORD)

    def test_logged_in_user_redirected_from_register(self):
        self.client.force_login(make_student())
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("accounts:dashboard"), fetch_redirect_response=False)


# ---------------------------------------------------------------------------
# Login and logout
# ---------------------------------------------------------------------------

class LoginLogoutTests(TestCase):
    login_url = reverse("accounts:login")
    logout_url = reverse("accounts:logout")

    def setUp(self):
        self.student = make_student()

    def test_login_success_redirects_to_dashboard(self):
        response = self.client.post(self.login_url, {"username": "student@cit.edu", "password": PASSWORD})
        self.assertRedirects(response, reverse("accounts:dashboard"), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.student.pk)

    def test_login_email_is_case_insensitive(self):
        response = self.client.post(self.login_url, {"username": "STUDENT@CIT.EDU", "password": PASSWORD})
        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_wrong_password_shows_generic_message(self):
        response = self.client.post(self.login_url, {"username": "student@cit.edu", "password": "wrong-pass"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid email or password.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_unknown_email_shows_same_message(self):
        response = self.client.post(self.login_url, {"username": "nobody@cit.edu", "password": PASSWORD})
        self.assertContains(response, "Invalid email or password.")

    def test_login_respects_safe_next_and_ignores_external_next(self):
        response = self.client.post(
            f"{self.login_url}?next=/accounts/profile/",
            {"username": "student@cit.edu", "password": PASSWORD, "next": "/accounts/profile/"},
        )
        self.assertRedirects(response, "/accounts/profile/", fetch_redirect_response=False)

        self.client.logout()
        response = self.client.post(
            self.login_url,
            {"username": "student@cit.edu", "password": PASSWORD, "next": "https://evil.example.com/"},
        )
        self.assertRedirects(response, reverse("accounts:dashboard"), fetch_redirect_response=False)

    def test_logged_in_user_redirected_from_login(self):
        self.client.force_login(self.student)
        response = self.client.get(self.login_url)
        self.assertRedirects(response, reverse("accounts:dashboard"), fetch_redirect_response=False)

    def test_logout_ends_session_and_shows_message(self):
        self.client.force_login(self.student)
        response = self.client.post(self.logout_url, follow=True)

        self.assertRedirects(response, self.login_url)
        self.assertContains(response, "You have been logged out.")
        self.assertNotIn("_auth_user_id", self.client.session)

        # Protected page now sends us back to login
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(self.login_url))

    def test_logout_requires_post(self):
        self.client.force_login(self.student)
        response = self.client.get(self.logout_url)
        self.assertEqual(response.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)


# ---------------------------------------------------------------------------
# Dashboards and access control (BR-18)
# ---------------------------------------------------------------------------

class AccessControlTests(TestCase):
    def setUp(self):
        self.student = make_student()
        self.staff = make_staff()

    def test_anonymous_users_redirected_to_login_with_next(self):
        protected = [
            reverse("accounts:dashboard"),
            reverse("accounts:student_dashboard"),
            reverse("accounts:staff_dashboard"),
            reverse("accounts:profile"),
            reverse("accounts:profile_edit"),
            reverse("accounts:password_change"),
        ]
        for url in protected:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(
                    response, f"{reverse('accounts:login')}?next={url}", fetch_redirect_response=False
                )

    def test_dashboard_router_sends_student_to_student_dashboard(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertRedirects(response, reverse("accounts:student_dashboard"))

    def test_dashboard_router_sends_staff_to_staff_dashboard(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertRedirects(response, reverse("accounts:staff_dashboard"))

    def test_student_sees_own_dashboard(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("accounts:student_dashboard"))
        self.assertContains(response, "Welcome, Stu Dent")
        self.assertContains(response, "Browse Menu")

    def test_staff_sees_own_dashboard(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("accounts:staff_dashboard"))
        self.assertContains(response, "Welcome, Canteen Staff")
        self.assertContains(response, "Incoming Orders")

    def test_student_blocked_from_staff_dashboard(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("accounts:staff_dashboard"))
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "403.html")
        self.assertContains(response, "permission to view this page", status_code=403)

    def test_staff_blocked_from_student_dashboard(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("accounts:student_dashboard"))
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "403.html")


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

class ProfileTests(TestCase):
    def setUp(self):
        self.alice = make_student(email="alice@cit.edu", full_name="Alice")
        self.bob = make_student(email="bob@cit.edu", full_name="Bob")
        self.client.force_login(self.alice)

    def test_profile_shows_own_details(self):
        response = self.client.get(reverse("accounts:profile"))
        self.assertContains(response, "Alice")
        self.assertContains(response, "alice@cit.edu")
        self.assertContains(response, "Student")
        self.assertNotContains(response, "bob@cit.edu")

    def test_profile_edit_only_changes_request_user(self):
        response = self.client.post(
            reverse("accounts:profile_edit"),
            {"full_name": "  Alice Updated  ", "email": "Alice.New@CIT.edu"},
            follow=True,
        )
        self.assertRedirects(response, reverse("accounts:profile"))
        self.assertContains(response, "Profile updated successfully.")

        self.alice.refresh_from_db()
        self.bob.refresh_from_db()
        self.assertEqual(self.alice.full_name, "Alice Updated")
        self.assertEqual(self.alice.email, "alice.new@cit.edu")
        self.assertEqual(self.bob.full_name, "Bob")          # untouched
        self.assertEqual(self.bob.email, "bob@cit.edu")      # untouched

    def test_profile_edit_cannot_change_role_or_permissions(self):
        self.client.post(
            reverse("accounts:profile_edit"),
            {"full_name": "Alice", "email": "alice@cit.edu",
             "role": "STAFF", "is_staff": "on", "is_superuser": "on"},
        )
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.role, User.Role.STUDENT)
        self.assertFalse(self.alice.is_staff)
        self.assertFalse(self.alice.is_superuser)

    def test_profile_edit_rejects_someone_elses_email(self):
        response = self.client.post(
            reverse("accounts:profile_edit"), {"full_name": "Alice", "email": "BOB@cit.edu"}
        )
        self.assertContains(response, "An account with this email already exists.")
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.email, "alice@cit.edu")

    def test_profile_edit_allows_keeping_own_email(self):
        response = self.client.post(
            reverse("accounts:profile_edit"), {"full_name": "Alice B.", "email": "ALICE@cit.edu"}
        )
        self.assertRedirects(response, reverse("accounts:profile"), fetch_redirect_response=False)

    def test_password_change_keeps_user_logged_in(self):
        new_password = "Canteen#Pass2027"
        response = self.client.post(
            reverse("accounts:password_change"),
            {"old_password": PASSWORD, "new_password1": new_password, "new_password2": new_password},
        )
        self.assertRedirects(response, reverse("accounts:password_change_done"))

        self.alice.refresh_from_db()
        self.assertTrue(self.alice.check_password(new_password))

        # Still logged in: a protected page loads instead of redirecting to login
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 200)

    def test_password_change_rejects_wrong_old_password(self):
        response = self.client.post(
            reverse("accounts:password_change"),
            {"old_password": "wrong", "new_password1": "Canteen#Pass2027", "new_password2": "Canteen#Pass2027"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("old_password", response.context["form"].errors)
        self.alice.refresh_from_db()
        self.assertTrue(self.alice.check_password(PASSWORD))
