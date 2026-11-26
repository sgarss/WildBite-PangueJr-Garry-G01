from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse

from accounts.tests import make_staff, make_student
from menu.models import Category, MenuItem

from . import services
from .models import Order, OrderStatus, Payment


# Security and validation checks for the core feature (food ordering)
class CoreFeatureSecurityTests(TestCase):
    def setUp(self):
        self.student = make_student()
        self.other = make_student(email="other@cit.edu", first_name="Other", last_name="Student")
        self.staff = make_staff()
        self.meals = Category.objects.create(name="Rice Meals")
        self.adobo = MenuItem.objects.create(category=self.meals, name="Chicken Adobo", price=Decimal("65.00"))
        self.order = services.place_order(self.student, {self.adobo.pk: 2})
        self.others_order = services.place_order(self.other, {self.adobo.pk: 1})

    def order_url(self, name, order=None):
        return reverse(name, args=[(order or self.order).pk])

    def place_order_form(self, client, quantities):
        url = reverse("orders:place")
        token = client.get(url).context["order_token"]
        return client.post(url, {**quantities, "order_token": token}, follow=True)

    # Valid input

    def test_valid_order_goes_through_every_step(self):
        self.client.force_login(self.student)
        response = self.place_order_form(self.client, {f"qty_{self.adobo.pk}": 3})
        order = Order.objects.filter(user=self.student).latest("order_id")
        self.assertContains(response, f"Order {order.order_number} placed.")
        self.assertEqual(order.total_amount, Decimal("195.00"))

        self.client.force_login(self.staff)
        for status in ["PENDING", "PREPARING"]:
            self.client.post(self.order_url("orders:advance_status", order), {"current_status": status})
        self.client.post(self.order_url("orders:record_payment", order))
        self.client.post(self.order_url("orders:advance_status", order), {"current_status": "READY"})

        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.COMPLETED)
        self.assertEqual(order.payment.payment_status, Payment.Status.PAID)
        self.assertEqual(order.status_history.count(), 4)

    # Invalid input

    def test_invalid_order_input_is_rejected(self):
        self.client.force_login(self.student)
        before = Order.objects.count()
        checks = [
            ({f"qty_{self.adobo.pk}": "abc"}, "Enter a whole number."),
            ({f"qty_{self.adobo.pk}": "-1"}, "Ensure this value is greater than or equal to 0."),
            ({f"qty_{self.adobo.pk}": "21"}, "Ensure this value is less than or equal to 20."),
            ({f"qty_{self.adobo.pk}": "0"}, "Choose at least one menu item."),
        ]
        for data, error in checks:
            with self.subTest(data=data):
                self.assertContains(self.place_order_form(self.client, data), error)
        self.assertEqual(Order.objects.count(), before)

    def test_invalid_menu_input_is_rejected(self):
        self.client.force_login(self.staff)
        item = {"category": self.meals.pk, "name": "Pork Sisig", "price": "0"}
        response = self.client.post(reverse("menu:item_add"), item)
        self.assertContains(response, "Price must be greater than zero.")
        response = self.client.post(reverse("menu:item_add"), {**item, "price": "75", "name": "chicken adobo"})
        self.assertContains(response, "already exists")
        response = self.client.post(reverse("menu:category_add"), {"name": ""})
        self.assertContains(response, "This field is required.")
        self.assertEqual(MenuItem.objects.count(), 1)
        self.assertEqual(Category.objects.count(), 1)

    def test_user_text_is_escaped_in_pages(self):
        Category.objects.create(name="<script>alert(1)</script>")
        self.client.force_login(self.staff)
        response = self.client.get(reverse("menu:category_list"))
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_search_text_is_not_run_as_sql(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("orders:staff_orders"), {"q": "' OR 1=1 --"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No orders match your search.")

    # Login required

    def test_every_page_needs_login(self):
        pages = [
            reverse("accounts:dashboard"),
            reverse("accounts:profile"),
            reverse("accounts:profile_edit"),
            reverse("accounts:profile_photo"),
            reverse("accounts:password_change"),
            reverse("menu:list"),
            reverse("menu:item_add"),
            reverse("menu:item_edit", args=[self.adobo.pk]),
            reverse("menu:item_delete", args=[self.adobo.pk]),
            reverse("menu:category_list"),
            reverse("menu:category_add"),
            reverse("menu:category_edit", args=[self.meals.pk]),
            reverse("menu:category_delete", args=[self.meals.pk]),
            reverse("orders:my_orders"),
            reverse("orders:place"),
            reverse("orders:staff_orders"),
            reverse("orders:sales_report"),
            self.order_url("orders:detail"),
            self.order_url("orders:edit"),
            self.order_url("orders:cancel"),
        ]
        login_url = reverse("accounts:login")
        for url in pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, f"{login_url}?next={url}", fetch_redirect_response=False)

    def test_actions_need_login(self):
        actions = [
            self.order_url("orders:advance_status"),
            self.order_url("orders:record_payment"),
            self.order_url("orders:cancel"),
            reverse("menu:item_toggle", args=[self.adobo.pk]),
            reverse("menu:item_delete", args=[self.adobo.pk]),
        ]
        for url in actions:
            with self.subTest(url=url):
                response = self.client.post(url)
                self.assertTrue(response["Location"].startswith(reverse("accounts:login")))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.PENDING)
        self.assertTrue(MenuItem.objects.get(pk=self.adobo.pk).is_available)

    # Blocked access

    def test_student_cannot_reach_another_students_order(self):
        self.client.force_login(self.student)
        for name in ["orders:detail", "orders:edit", "orders:cancel"]:
            with self.subTest(url=name):
                url = self.order_url(name, self.others_order)
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.post(url, {f"qty_{self.adobo.pk}": 5}).status_code, 404)
        self.others_order.refresh_from_db()
        self.assertEqual(self.others_order.items.get().quantity, 1)
        self.assertNotContains(self.client.get(reverse("orders:my_orders")), self.others_order.order_number)

    def test_students_cannot_use_staff_pages(self):
        self.client.force_login(self.student)
        dashboard = reverse("accounts:dashboard")
        for url in [
            reverse("orders:staff_orders"),
            reverse("orders:sales_report"),
            reverse("menu:item_add"),
            reverse("menu:category_list"),
            reverse("accounts:staff_dashboard"),
        ]:
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), dashboard, fetch_redirect_response=False)
        for url in [
            self.order_url("orders:advance_status"),
            self.order_url("orders:record_payment"),
            reverse("menu:item_toggle", args=[self.adobo.pk]),
            reverse("menu:item_delete", args=[self.adobo.pk]),
        ]:
            with self.subTest(url=url):
                self.assertRedirects(self.client.post(url), dashboard, fetch_redirect_response=False)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.PENDING)
        self.assertTrue(MenuItem.objects.filter(pk=self.adobo.pk, is_available=True).exists())

    def test_staff_cannot_use_student_pages(self):
        self.client.force_login(self.staff)
        for url in [reverse("orders:place"), reverse("orders:my_orders"), self.order_url("orders:edit")]:
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), reverse("accounts:dashboard"), fetch_redirect_response=False)
        self.assertRedirects(
            self.client.post(self.order_url("orders:cancel")),
            reverse("accounts:dashboard"),
            fetch_redirect_response=False,
        )
        self.assertTrue(Order.objects.filter(pk=self.order.pk).exists())

    # Invalid IDs

    def test_missing_ids_return_404(self):
        self.client.force_login(self.staff)
        for name in ["orders:detail", "menu:item_edit", "menu:item_delete", "menu:category_edit", "menu:category_delete"]:
            with self.subTest(url=name):
                self.assertEqual(self.client.get(reverse(name, args=[99999])).status_code, 404)
        for name in ["orders:advance_status", "orders:record_payment", "menu:item_toggle"]:
            with self.subTest(url=name):
                self.assertEqual(self.client.post(reverse(name, args=[99999])).status_code, 404)

        self.client.force_login(self.student)
        for name in ["orders:detail", "orders:edit", "orders:cancel"]:
            with self.subTest(url=name):
                self.assertEqual(self.client.get(reverse(name, args=[99999])).status_code, 404)

    def test_non_numeric_ids_return_404(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get("/orders/abc/").status_code, 404)
        self.assertEqual(self.client.get("/menu/items/abc/edit/").status_code, 404)

    # Changes only by POST, with a CSRF token

    def test_actions_reject_get(self):
        self.client.force_login(self.staff)
        for url in [
            self.order_url("orders:advance_status"),
            self.order_url("orders:record_payment"),
            reverse("menu:item_toggle", args=[self.adobo.pk]),
            reverse("accounts:logout"),
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.PENDING)

    def test_get_on_delete_pages_only_asks_for_confirmation(self):
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse("menu:item_delete", args=[self.adobo.pk])), "Delete menu item?")
        self.client.force_login(self.student)
        self.assertContains(self.client.get(self.order_url("orders:cancel")), "Yes, cancel order")
        self.assertTrue(MenuItem.objects.filter(pk=self.adobo.pk).exists())
        self.assertTrue(Order.objects.filter(pk=self.order.pk).exists())

    def test_post_without_csrf_token_is_rejected(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.student)
        before = Order.objects.count()
        token = client.get(reverse("orders:place")).context["order_token"]
        response = client.post(reverse("orders:place"), {f"qty_{self.adobo.pk}": 1, "order_token": token})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(client.post(self.order_url("orders:cancel")).status_code, 403)
        self.assertEqual(Order.objects.count(), before)

        client.force_login(self.staff)
        response = client.post(self.order_url("orders:advance_status"), {"current_status": "PENDING"})
        self.assertEqual(response.status_code, 403)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.PENDING)
