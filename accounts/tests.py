import io
import shutil
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

User = get_user_model()

PASSWORD = "Wildbite#2026x"
TEST_MEDIA_ROOT = tempfile.mkdtemp()


# Test helpers
def make_student(email="student@cit.edu", first_name="Stu", last_name="Dent"):
    return User.objects.create_user(email=email, password=PASSWORD, first_name=first_name, last_name=last_name)


def make_staff(email="staff@cit.edu", first_name="Canteen", last_name="Staff"):
    return User.objects.create_user(
        email=email, password=PASSWORD, first_name=first_name, last_name=last_name, role=User.Role.STAFF
    )


# Small real image for upload tests
def make_image(name="photo.png", fmt="PNG", color="red"):
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), color).save(buffer, fmt)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=f"image/{fmt.lower()}")


class UserModelTests(TestCase):
    def test_create_user_defaults_to_student_and_hashes_password(self):
        user = User.objects.create_user(email="Mixed.Case@CIT.edu", password=PASSWORD, first_name="A", last_name="B")
        self.assertEqual(user.email, "mixed.case@cit.edu")
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertFalse(user.is_staff)
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertTrue(user.is_student)
        self.assertFalse(user.is_canteen_staff)

    def test_create_superuser_is_staff_role(self):
        admin = User.objects.create_superuser(email="admin@cit.edu", password=PASSWORD, first_name="Ad", last_name="Min")
        self.assertEqual(admin.role, User.Role.STAFF)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_database_check_constraint_rejects_unknown_role(self):
        user = make_student()
        # DB should reject an unknown role
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=user.pk).update(role="ADMIN")

    def test_database_rejects_duplicate_email(self):
        make_student(email="dup@cit.edu")
        # DB should reject a duplicate email
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(email="dup@cit.edu", password=PASSWORD, first_name="B", last_name="C")


class RegistrationTests(TestCase):
    url = reverse("accounts:register")

    def form_data(self, **overrides):
        data = {
            "first_name": "Juan",
            "last_name": "Dela Cruz",
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

        user = User.objects.get(email="juan@cit.edu")
        self.assertEqual(user.first_name, "Juan")
        self.assertEqual(user.last_name, "Dela Cruz")
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
        response = self.client.post(self.url, {"first_name": "   ", "email": "not-an-email"})
        form = response.context["form"]
        self.assertIn("first_name", form.errors)
        self.assertIn("last_name", form.errors)
        self.assertFormError(form, "email", "Enter a valid email address.")
        self.assertIn("password1", form.errors)
        self.assertIn("password2", form.errors)

    def test_weak_password_rejected(self):
        response = self.client.post(self.url, self.form_data(password1="12345", password2="12345"))
        self.assertIn("password2", response.context["form"].errors)
        self.assertFalse(User.objects.exists())

    def test_entered_values_kept_but_passwords_not_redisplayed(self):
        response = self.client.post(self.url, self.form_data(password2="Different#2026x"))
        self.assertContains(response, 'value="Juan"')
        self.assertContains(response, 'value="Dela Cruz"')
        self.assertNotContains(response, PASSWORD)

    def test_logged_in_user_redirected_from_register(self):
        self.client.force_login(make_student())
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("accounts:dashboard"), fetch_redirect_response=False)


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

        # External next URL is ignored
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

        # Protected page needs login again
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(self.login_url))

    def test_logout_requires_post(self):
        self.client.force_login(self.student)
        response = self.client.get(self.logout_url)
        self.assertEqual(response.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)


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

    def test_student_redirected_from_staff_dashboard(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("accounts:staff_dashboard"), follow=True)
        self.assertRedirects(response, reverse("accounts:student_dashboard"))
        self.assertNotContains(response, "permission")
        self.assertNotContains(response, "Incoming Orders")

    def test_staff_redirected_from_student_dashboard(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("accounts:student_dashboard"), follow=True)
        self.assertRedirects(response, reverse("accounts:staff_dashboard"))
        self.assertNotContains(response, "permission")
        self.assertNotContains(response, "Browse Menu")

    def test_student_redirected_from_admin_site(self):
        self.client.force_login(self.student)
        for url in ["/admin/", "/admin/accounts/user/"]:
            with self.subTest(url=url):
                response = self.client.get(url, follow=True)
                self.assertRedirects(response, reverse("accounts:student_dashboard"))
                self.assertNotContains(response, "not authorized")

    def test_staff_without_admin_access_redirected_from_admin_site(self):
        self.client.force_login(self.staff)
        response = self.client.get("/admin/", follow=True)
        self.assertRedirects(response, reverse("accounts:staff_dashboard"))
        self.assertNotContains(response, "not authorized")

    def test_staff_with_is_staff_but_not_superuser_redirected_from_admin_site(self):
        self.staff.is_staff = True
        self.staff.save()
        self.client.force_login(self.staff)
        for url in ["/admin/", "/admin/accounts/user/"]:
            with self.subTest(url=url):
                response = self.client.get(url, follow=True)
                self.assertRedirects(response, reverse("accounts:staff_dashboard"))
                self.assertNotContains(response, "permission")

    def test_admin_can_open_admin_site(self):
        admin = User.objects.create_superuser(email="admin@cit.edu", password=PASSWORD, first_name="Ad", last_name="Min")
        self.client.force_login(admin)
        self.assertEqual(self.client.get("/admin/").status_code, 200)
        self.assertEqual(self.client.get("/admin/accounts/user/").status_code, 200)

    def test_anonymous_sees_admin_login(self):
        response = self.client.get("/admin/", follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/login.html")


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ProfileTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.alice = make_student(email="alice@cit.edu", first_name="Alice", last_name="Reyes")
        self.bob = make_student(email="bob@cit.edu", first_name="Bob", last_name="Santos")
        self.client.force_login(self.alice)

    # Submit the edit form with Alice's current values plus overrides
    def edit(self, follow=False, **overrides):
        data = {"first_name": "Alice", "last_name": "Reyes", "email": "alice@cit.edu", "contact_number": ""}
        data.update(overrides)
        return self.client.post(reverse("accounts:profile_edit"), data, follow=follow)

    def get_photo_bytes(self):
        response = self.client.get(reverse("accounts:profile_photo"))
        content = b"".join(response.streaming_content) if response.status_code == 200 else b""
        return response.status_code, content

    def test_profile_shows_own_details(self):
        response = self.client.get(reverse("accounts:profile"))
        self.assertContains(response, "Alice")
        self.assertContains(response, "Reyes")
        self.assertContains(response, "alice@cit.edu")
        self.assertContains(response, "Student")
        self.assertNotContains(response, "bob@cit.edu")

    def test_update_name(self):
        response = self.edit(follow=True, first_name="  Alicia  ", last_name=" Cruz ")
        self.assertRedirects(response, reverse("accounts:profile"))
        self.assertContains(response, "Profile updated successfully.")
        self.assertContains(response, "Alicia")
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.first_name, "Alicia")
        self.assertEqual(self.alice.last_name, "Cruz")

    def test_blank_name_rejected(self):
        response = self.edit(first_name="   ", last_name="")
        self.assertContains(response, "Please fix the errors below.")
        self.assertIn("first_name", response.context["form"].errors)
        self.assertIn("last_name", response.context["form"].errors)
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.first_name, "Alice")

    def test_update_email(self):
        self.edit(email="Alice.New@CIT.edu")
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.email, "alice.new@cit.edu")

    def test_keep_own_email(self):
        response = self.edit(email="ALICE@cit.edu")
        self.assertRedirects(response, reverse("accounts:profile"), fetch_redirect_response=False)

    def test_invalid_email_rejected(self):
        response = self.edit(email="not-an-email")
        self.assertFormError(response.context["form"], "email", "Enter a valid email address.")
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.email, "alice@cit.edu")

    def test_duplicate_email_rejected(self):
        response = self.edit(email="BOB@cit.edu")
        self.assertContains(response, "An account with this email already exists.")
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.email, "alice@cit.edu")

    def test_update_contact_number(self):
        response = self.edit(follow=True, contact_number="0917 123 4567")
        self.assertContains(response, "09171234567")
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.contact_number, "09171234567")

    def test_invalid_contact_number_rejected(self):
        response = self.edit(contact_number="call me")
        self.assertContains(response, "Enter a valid contact number")
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.contact_number, "")

    def test_clear_contact_number(self):
        self.edit(contact_number="09171234567")
        self.edit(contact_number="")
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.contact_number, "")

    def test_upload_photo(self):
        response = self.edit(follow=True, profile_photo=make_image())
        self.assertContains(response, "Profile updated successfully.")
        self.alice.refresh_from_db()
        self.assertTrue(self.alice.profile_photo.name.startswith("profile_photos/"))
        status, content = self.get_photo_bytes()
        self.assertEqual(status, 200)
        self.assertTrue(content.startswith(b"\x89PNG"))

    def test_change_photo_deletes_old_file(self):
        self.edit(profile_photo=make_image(color="red"))
        self.alice.refresh_from_db()
        old_name = self.alice.profile_photo.name

        self.edit(profile_photo=make_image(name="new.jpg", fmt="JPEG", color="blue"))
        self.alice.refresh_from_db()
        storage = self.alice.profile_photo.storage
        self.assertNotEqual(self.alice.profile_photo.name, old_name)
        self.assertTrue(storage.exists(self.alice.profile_photo.name))
        self.assertFalse(storage.exists(old_name))

    def test_empty_upload_keeps_current_photo(self):
        self.edit(profile_photo=make_image())
        self.alice.refresh_from_db()
        name = self.alice.profile_photo.name
        self.edit(first_name="Alicia")
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.profile_photo.name, name)

    def test_remove_photo(self):
        self.edit(profile_photo=make_image())
        self.alice.refresh_from_db()
        old_name = self.alice.profile_photo.name
        self.edit(remove_photo="on")
        self.alice.refresh_from_db()
        self.assertFalse(self.alice.profile_photo)
        self.assertFalse(self.alice.profile_photo.storage.exists(old_name))
        self.assertEqual(self.get_photo_bytes()[0], 404)

    def test_non_image_upload_rejected(self):
        fake = SimpleUploadedFile("photo.png", b"this is not an image", content_type="image/png")
        response = self.edit(profile_photo=fake)
        self.assertIn("profile_photo", response.context["form"].errors)
        self.alice.refresh_from_db()
        self.assertFalse(self.alice.profile_photo)

    def test_disallowed_image_type_rejected(self):
        response = self.edit(profile_photo=make_image(name="photo.bmp", fmt="BMP"))
        self.assertIn("profile_photo", response.context["form"].errors)
        self.alice.refresh_from_db()
        self.assertFalse(self.alice.profile_photo)

    def test_too_large_photo_rejected(self):
        with mock.patch("accounts.forms.MAX_PHOTO_SIZE", 10):
            response = self.edit(profile_photo=make_image())
        self.assertContains(response, "Photo must be 2 MB or smaller.")
        self.alice.refresh_from_db()
        self.assertFalse(self.alice.profile_photo)

    def test_cannot_open_another_profile_by_url(self):
        for url in [
            f"/accounts/profile/{self.bob.pk}/",
            f"/accounts/profile/{self.bob.pk}/edit/",
            f"/accounts/profile/photo/{self.bob.pk}/",
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)

        response = self.client.get(f"{reverse('accounts:profile')}?user_id={self.bob.pk}&pk={self.bob.pk}")
        self.assertContains(response, "alice@cit.edu")
        self.assertNotContains(response, "bob@cit.edu")

    def test_photo_view_only_returns_own_photo(self):
        self.client.force_login(self.bob)
        self.edit(profile_photo=make_image(color="blue"), first_name="Bob", last_name="Santos", email="bob@cit.edu")
        _, bob_bytes = self.get_photo_bytes()

        self.client.force_login(self.alice)
        self.assertEqual(self.get_photo_bytes()[0], 404)
        self.edit(profile_photo=make_image(color="red"))
        status, alice_bytes = self.get_photo_bytes()
        self.assertEqual(status, 200)
        self.assertNotEqual(alice_bytes, bob_bytes)

    def test_navbar_shows_profile_picture_or_initials(self):
        response = self.client.get(reverse("accounts:student_dashboard"))
        self.assertContains(response, 'class="avatar avatar-nav">AR</span>', html=False)
        self.assertNotContains(response, ">Profile</a>")

        self.edit(profile_photo=make_image())
        response = self.client.get(reverse("accounts:student_dashboard"))
        self.assertContains(response, f'src="{reverse("accounts:profile_photo")}?v=')
        self.assertContains(response, 'aria-label="My profile"')

    def test_anonymous_cannot_view_profile_or_photo(self):
        self.client.logout()
        for name in ["accounts:profile", "accounts:profile_edit", "accounts:profile_photo"]:
            with self.subTest(url=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response["Location"].startswith(reverse("accounts:login")))

    def test_cannot_edit_another_user_with_request_params(self):
        self.edit(first_name="Changed", user_id=self.bob.pk, pk=self.bob.pk, user=self.bob.pk,
                  profile_photo=make_image())
        self.bob.refresh_from_db()
        self.alice.refresh_from_db()
        self.assertEqual(self.bob.first_name, "Bob")
        self.assertEqual(self.bob.email, "bob@cit.edu")
        self.assertFalse(self.bob.profile_photo)
        # Only the logged-in user changed
        self.assertEqual(self.alice.first_name, "Changed")

    def test_profile_edit_cannot_change_role_or_permissions(self):
        self.edit(role="STAFF", is_staff="on", is_superuser="on")
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.role, User.Role.STUDENT)
        self.assertFalse(self.alice.is_staff)
        self.assertFalse(self.alice.is_superuser)

    def test_changes_saved_after_logout_and_login(self):
        self.edit(first_name="Alicia", last_name="Cruz", email="alicia@cit.edu",
                  contact_number="09171234567", profile_photo=make_image())
        self.client.post(reverse("accounts:logout"))
        self.client.post(reverse("accounts:login"), {"username": "alicia@cit.edu", "password": PASSWORD})

        response = self.client.get(reverse("accounts:profile"))
        for text in ["Alicia", "Cruz", "alicia@cit.edu", "09171234567"]:
            self.assertContains(response, text)
        self.assertEqual(self.get_photo_bytes()[0], 200)

    def test_password_change_keeps_user_logged_in(self):
        new_password = "Canteen#Pass2027"
        response = self.client.post(
            reverse("accounts:password_change"),
            {"old_password": PASSWORD, "new_password1": new_password, "new_password2": new_password},
        )
        self.assertRedirects(response, reverse("accounts:password_change_done"))

        self.alice.refresh_from_db()
        self.assertTrue(self.alice.check_password(new_password))

        # Still logged in
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
