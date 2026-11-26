from django.conf import settings
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.views.defaults import server_error

from accounts.tests import make_student


# Tests always run with DEBUG off, like the real site
class ErrorPageTests(TestCase):
    def test_debug_is_off_in_tests(self):
        self.assertFalse(settings.DEBUG)

    def test_unknown_url_shows_custom_404(self):
        response = self.client.get("/this-page-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "Page not found", status_code=404)
        self.assertNotContains(response, "Traceback", status_code=404)

    def test_missing_order_shows_custom_404(self):
        self.client.force_login(make_student())
        response = self.client.get(reverse("orders:detail", args=[99999]))
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "Go to my dashboard", status_code=404)

    def test_server_error_shows_custom_500(self):
        response = server_error(RequestFactory().get("/"))
        self.assertEqual(response.status_code, 500)
        self.assertIn(b"Something went wrong", response.content)
        self.assertNotIn(b"Traceback", response.content)

    def test_missing_csrf_token_shows_friendly_page(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse("accounts:login"), {"username": "a@cit.edu", "password": "x"})
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "This form has expired", status_code=403)
