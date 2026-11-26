import re
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import RestrictedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from accounts.tests import PASSWORD, make_staff, make_student
from menu.models import Category, MenuItem

from . import services
from .models import Order, OrderItem, OrderStatus, OrderStatusHistory, Payment


# Shared users and menu for the order tests
class OrderSetup:
    def setUp(self):
        self.student = make_student()
        self.other = make_student(email="other@cit.edu", first_name="Other", last_name="Student")
        self.staff = make_staff()
        meals = Category.objects.create(name="Rice Meals")
        drinks = Category.objects.create(name="Drinks")
        self.adobo = MenuItem.objects.create(category=meals, name="Chicken Adobo", price=Decimal("65.00"))
        self.tea = MenuItem.objects.create(category=drinks, name="Iced Tea", price=Decimal("25.50"))
        self.sisig = MenuItem.objects.create(
            category=meals, name="Pork Sisig", price=Decimal("75.00"), is_available=False
        )

    def place(self, student=None, quantities=None):
        return services.place_order(student or self.student, quantities or {self.adobo.pk: 2})

    def set_status(self, order, status):
        Order.objects.filter(pk=order.pk).update(status=status)
        order.refresh_from_db()

    def detail_url(self, order):
        return reverse("orders:detail", args=[order.pk])


class OrderDatabaseTests(OrderSetup, TestCase):
    def test_tables_match_sdd(self):
        tables = [model._meta.db_table for model in (Order, OrderItem, OrderStatusHistory, Payment)]
        self.assertEqual(tables, ["orders", "order_items", "order_status_history", "payments"])

    def test_order_number_must_be_unique(self):
        order = self.place()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Order.objects.create(user=self.student, order_number=order.order_number, total_amount=0)

    def test_status_must_be_one_of_four(self):
        order = self.place()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Order.objects.filter(pk=order.pk).update(status="CANCELLED")

    def test_quantity_must_be_at_least_one(self):
        order = self.place()
        with self.assertRaises(IntegrityError), transaction.atomic():
            order.items.update(quantity=0)

    def test_menu_item_only_once_per_order(self):
        order = self.place()
        with self.assertRaises(IntegrityError), transaction.atomic():
            OrderItem.objects.create(order=order, menu_item=self.adobo, quantity=1, unit_price=Decimal("65"))

    def test_paid_at_only_when_paid(self):
        order = self.place()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Payment.objects.filter(order=order).update(payment_status="PAID")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Payment.objects.filter(order=order).update(paid_at=timezone.now())

    def test_foreign_keys_have_sdd_on_delete_rules(self):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT cl.relname || '.' || att.attname, con.confdeltype
                FROM pg_constraint con
                JOIN pg_class cl ON cl.oid = con.conrelid
                JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = ANY (con.conkey)
                WHERE con.contype = 'f'
                  AND cl.relname IN ('order_items', 'order_status_history', 'payments')
                  AND att.attname IN ('order_id', 'menu_item_id')
            """)
            rules = dict(cursor.fetchall())
        self.assertEqual(rules, {
            "order_items.order_id": "c",
            "order_items.menu_item_id": "r",
            "order_status_history.order_id": "c",
            "payments.order_id": "c",
        })

    def test_menu_item_in_an_order_cannot_be_deleted(self):
        self.place()
        with self.assertRaises(RestrictedError):
            self.adobo.delete()

        self.client.force_login(self.staff)
        response = self.client.post(reverse("menu:item_delete", args=[self.adobo.pk]), follow=True)
        self.assertContains(response, "is part of existing orders")
        self.assertTrue(MenuItem.objects.filter(pk=self.adobo.pk).exists())


class PlaceOrderTests(OrderSetup, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.student)
        self.url = reverse("orders:place")

    # Open the order page and send its form, like a browser would
    def submit(self, data, token=None, follow=False):
        if token is None:
            token = self.client.get(self.url).context["order_token"]
        return self.client.post(self.url, {**data, "order_token": token}, follow=follow)

    def test_place_order(self):
        response = self.submit({f"qty_{self.adobo.pk}": 2, f"qty_{self.tea.pk}": 1}, follow=True)
        order = Order.objects.get()
        self.assertRedirects(response, self.detail_url(order))
        self.assertContains(response, f"Order {order.order_number} placed.")

        self.assertRegex(order.order_number, r"^WB-\d{6}-001$")
        self.assertEqual(order.user, self.student)
        self.assertEqual(order.status, OrderStatus.PENDING)
        self.assertEqual(order.total_amount, Decimal("155.50"))
        self.assertEqual(
            sorted(order.items.values_list("menu_item__name", "quantity", "unit_price")),
            [("Chicken Adobo", 2, Decimal("65.00")), ("Iced Tea", 1, Decimal("25.50"))],
        )
        # Status history and payment are created with the order
        history = order.status_history.get()
        self.assertEqual((history.status, history.changed_by), (OrderStatus.PENDING, self.student))
        self.assertEqual(order.payment.payment_status, Payment.Status.UNPAID)
        self.assertEqual(order.payment.amount, Decimal("155.50"))
        self.assertIsNone(order.payment.paid_at)

    def test_order_numbers_count_up(self):
        first = self.place()
        second = self.place(student=self.other)
        self.assertTrue(first.order_number.endswith("-001"))
        self.assertTrue(second.order_number.endswith("-002"))

    def test_later_price_change_does_not_affect_order(self):
        order = self.place()
        self.adobo.price = Decimal("80.00")
        self.adobo.save()
        order.refresh_from_db()
        self.assertEqual(order.items.get().unit_price, Decimal("65.00"))
        self.assertEqual(order.total_amount, Decimal("130.00"))

    def test_empty_order_rejected(self):
        response = self.submit({f"qty_{self.adobo.pk}": 0})
        self.assertContains(response, "Choose at least one menu item.")
        self.assertFalse(Order.objects.exists())

    def test_invalid_quantities_rejected(self):
        for quantity in ["-1", "21", "abc"]:
            with self.subTest(quantity=quantity):
                response = self.submit({f"qty_{self.adobo.pk}": quantity})
                self.assertContains(response, "Please fix the errors below.")
        self.assertFalse(Order.objects.exists())

    def test_unavailable_item_cannot_be_ordered(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Chicken Adobo")
        self.assertNotContains(response, "Pork Sisig")

        with self.assertRaisesMessage(ValidationError, "No longer available: Pork Sisig."):
            self.place(quantities={self.sisig.pk: 1})
        self.assertFalse(Order.objects.exists())

    def test_item_that_becomes_unavailable_is_rejected(self):
        token = self.client.get(self.url).context["order_token"]
        self.adobo.is_available = False
        self.adobo.save()
        response = self.submit({f"qty_{self.adobo.pk}": 1}, token=token)
        self.assertContains(response, "Choose at least one menu item.")
        self.assertFalse(Order.objects.exists())

    def test_same_form_cannot_be_sent_twice(self):
        token = self.client.get(self.url).context["order_token"]
        data = {f"qty_{self.adobo.pk}": 1}
        self.submit(data, token=token)
        response = self.submit(data, token=token, follow=True)
        self.assertRedirects(response, reverse("orders:my_orders"))
        self.assertContains(response, "This order was already submitted.")
        self.assertEqual(Order.objects.count(), 1)

    def test_order_without_token_is_rejected(self):
        response = self.client.post(self.url, {f"qty_{self.adobo.pk}": 1}, follow=True)
        self.assertContains(response, "This order was already submitted.")
        self.assertFalse(Order.objects.exists())

    def test_form_with_errors_gets_a_new_token(self):
        response = self.submit({f"qty_{self.adobo.pk}": 0})
        self.submit({f"qty_{self.adobo.pk}": 1}, token=response.context["order_token"])
        self.assertEqual(Order.objects.count(), 1)

    def test_two_open_tabs_both_work(self):
        first = self.client.get(self.url).context["order_token"]
        second = self.client.get(self.url).context["order_token"]
        self.submit({f"qty_{self.adobo.pk}": 1}, token=first)
        self.submit({f"qty_{self.tea.pk}": 1}, token=second)
        self.assertEqual(Order.objects.count(), 2)

    def test_staff_cannot_place_orders(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("accounts:dashboard"), fetch_redirect_response=False)

    def test_anonymous_redirected_to_login(self):
        self.client.logout()
        order = self.place()
        for url in [self.url, reverse("orders:my_orders"), self.detail_url(order), reverse("orders:staff_orders")]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertTrue(response["Location"].startswith(reverse("accounts:login")))


class StudentOrderTests(OrderSetup, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.student)

    def test_my_orders_shows_only_own_orders(self):
        mine = self.place()
        theirs = self.place(student=self.other)
        response = self.client.get(reverse("orders:my_orders"))
        self.assertContains(response, self.detail_url(mine))
        self.assertNotContains(response, self.detail_url(theirs))

    def test_cannot_open_or_change_another_students_order(self):
        theirs = self.place(student=self.other)
        self.assertEqual(self.client.get(self.detail_url(theirs)).status_code, 404)
        self.assertEqual(self.client.get(reverse("orders:edit", args=[theirs.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("orders:cancel", args=[theirs.pk])).status_code, 404)
        self.assertTrue(Order.objects.filter(pk=theirs.pk).exists())

    def test_completed_orders_show_in_history(self):
        order = self.place()
        self.set_status(order, OrderStatus.COMPLETED)
        content = self.client.get(reverse("orders:my_orders")).content.decode()
        self.assertIn("You have no current orders.", content)
        self.assertGreater(content.index(self.detail_url(order)), content.index("Order history"))

    def test_student_sees_status_and_payment(self):
        order = self.place()
        response = self.client.get(self.detail_url(order))
        self.assertContains(response, order.order_number)
        self.assertContains(response, "Pending")
        self.assertContains(response, "Unpaid")

    def test_edit_pending_order(self):
        order = self.place()
        self.adobo.price = Decimal("80.00")
        self.adobo.save()

        url = reverse("orders:edit", args=[order.pk])
        response = self.client.post(url, {f"qty_{self.adobo.pk}": 3, f"qty_{self.tea.pk}": 2}, follow=True)
        self.assertContains(response, f"Order {order.order_number} updated.")
        order.refresh_from_db()
        # Adobo keeps its original price, tea uses the current one
        self.assertEqual(order.total_amount, Decimal("246.00"))
        self.assertEqual(order.payment.amount, Decimal("246.00"))

        self.client.post(url, {f"qty_{self.tea.pk}": 1})
        self.assertEqual(list(order.items.values_list("menu_item__name", flat=True)), ["Iced Tea"])

    def test_unavailable_item_can_stay_but_not_increase(self):
        order = self.place()
        self.adobo.is_available = False
        self.adobo.save()
        url = reverse("orders:edit", args=[order.pk])

        response = self.client.post(url, {f"qty_{self.adobo.pk}": 3})
        self.assertContains(response, "No longer available: Chicken Adobo.")

        self.client.post(url, {f"qty_{self.adobo.pk}": 1})
        self.assertEqual(order.items.get().quantity, 1)

    def test_cannot_edit_after_preparing_starts(self):
        order = self.place()
        self.set_status(order, OrderStatus.PREPARING)
        response = self.client.get(reverse("orders:edit", args=[order.pk]), follow=True)
        self.assertContains(response, "Only pending orders can be changed.")
        with self.assertRaises(ValidationError):
            services.update_order(order, {self.adobo.pk: 5})

    def test_cancel_pending_order_deletes_everything(self):
        order = self.place()
        response = self.client.post(reverse("orders:cancel", args=[order.pk]), follow=True)
        self.assertRedirects(response, reverse("orders:my_orders"))
        self.assertContains(response, f"Order {order.order_number} was cancelled.")
        self.assertFalse(Order.objects.exists())
        self.assertFalse(OrderItem.objects.exists())
        self.assertFalse(OrderStatusHistory.objects.exists())
        self.assertFalse(Payment.objects.exists())

    def test_cannot_cancel_after_preparing_starts(self):
        order = self.place()
        self.set_status(order, OrderStatus.PREPARING)
        response = self.client.post(reverse("orders:cancel", args=[order.pk]), follow=True)
        self.assertContains(response, "Only pending orders can be cancelled.")
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())

    def test_cancel_asks_for_confirmation_first(self):
        order = self.place()
        url = reverse("orders:cancel", args=[order.pk])
        self.assertContains(self.client.get(self.detail_url(order)), f'href="{url}"')

        response = self.client.get(url)
        self.assertTemplateUsed(response, "orders/confirm_cancel.html")
        self.assertContains(response, f"Cancel order {order.order_number}?")
        self.assertContains(response, "2 &times; Chicken Adobo")
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())

    def test_confirm_page_not_shown_after_preparing_starts(self):
        order = self.place()
        self.set_status(order, OrderStatus.PREPARING)
        response = self.client.get(reverse("orders:cancel", args=[order.pk]), follow=True)
        self.assertRedirects(response, self.detail_url(order))
        self.assertContains(response, "Only pending orders can be cancelled.")

    def test_student_cannot_update_status_or_payment(self):
        order = self.place()
        for name in ["orders:advance_status", "orders:record_payment"]:
            with self.subTest(url=name):
                response = self.client.post(reverse(name, args=[order.pk]))
                self.assertRedirects(response, reverse("accounts:dashboard"), fetch_redirect_response=False)
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.PENDING)
        self.assertFalse(order.payment.is_paid)


class StaffOrderTests(OrderSetup, TestCase):
    def setUp(self):
        super().setUp()
        self.order = self.place()
        self.client.force_login(self.staff)

    def advance(self, current_status=None):
        self.order.refresh_from_db()
        data = {"current_status": current_status or self.order.status}
        return self.client.post(reverse("orders:advance_status", args=[self.order.pk]), data, follow=True)

    def pay(self):
        return self.client.post(reverse("orders:record_payment", args=[self.order.pk]), follow=True)

    def test_staff_sees_all_orders(self):
        other_order = self.place(student=self.other)
        response = self.client.get(reverse("orders:staff_orders"))
        self.assertContains(response, self.detail_url(self.order))
        self.assertContains(response, self.detail_url(other_order))
        self.assertContains(response, "Other Student")
        self.assertEqual(self.client.get(self.detail_url(other_order)).status_code, 200)

    def test_search_and_filters(self):
        link = f'href="{self.detail_url(self.order)}"'
        today = timezone.localdate().isoformat()
        checks = [
            ({"q": self.order.order_number[-3:]}, True),
            ({"q": "WB-000000"}, False),
            ({"status": "PENDING"}, True),
            ({"status": "READY"}, False),
            ({"date": today}, True),
            ({"date": "2020-01-01"}, False),
        ]
        for params, shown in checks:
            with self.subTest(params=params):
                content = self.client.get(reverse("orders:staff_orders"), params).content.decode()
                self.assertEqual(link in content, shown)

    def test_status_moves_forward_and_is_recorded(self):
        self.assertContains(self.advance(), "is now Preparing.")
        self.assertContains(self.advance(), "is now Ready for pickup.")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.READY)
        history = list(self.order.status_history.values_list("status", "changed_by"))
        self.assertEqual(history, [
            ("PENDING", self.student.pk),
            ("PREPARING", self.staff.pk),
            ("READY", self.staff.pk),
        ])

    def test_double_click_moves_status_only_once(self):
        self.advance(current_status="PENDING")
        response = self.advance(current_status="PENDING")
        self.assertContains(response, "This order was already moved to Preparing. Nothing was changed.")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.PREPARING)
        self.assertEqual(self.order.status_history.count(), 2)

    def test_status_button_sends_current_status(self):
        response = self.client.get(self.detail_url(self.order))
        self.assertContains(response, 'name="current_status" value="PENDING"')

    def test_invalid_filter_shows_error(self):
        response = self.client.get(reverse("orders:staff_orders"), {"date": "not-a-date"})
        self.assertContains(response, "Enter a valid date.")
        self.assertContains(response, "No orders match your search.")
        response = self.client.get(reverse("orders:staff_orders"), {"status": "CANCELLED"})
        self.assertContains(response, "Select a valid choice.")

    def test_cannot_complete_before_payment(self):
        self.set_status(self.order, OrderStatus.READY)
        self.assertContains(self.advance(), "Record the cash payment before completing this order.")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.READY)

    def test_record_payment_then_complete(self):
        self.set_status(self.order, OrderStatus.READY)
        self.assertContains(self.pay(), "Cash payment of ₱130.00 recorded")
        payment = Payment.objects.get(order=self.order)
        self.assertEqual(payment.payment_status, Payment.Status.PAID)
        self.assertEqual(payment.received_by, self.staff)
        self.assertIsNotNone(payment.paid_at)

        self.assertContains(self.advance(), "is now Completed.")
        self.assertContains(self.advance(), "This order is already completed.")

    def test_payment_only_when_ready(self):
        self.assertContains(self.pay(), "Cash can be recorded once the order is ready for pickup.")
        self.assertFalse(Payment.objects.get(order=self.order).is_paid)

    def test_payment_cannot_be_recorded_twice(self):
        self.set_status(self.order, OrderStatus.READY)
        self.pay()
        self.assertContains(self.pay(), "This order is already paid.")

    def test_detail_shows_next_action(self):
        self.assertContains(self.client.get(self.detail_url(self.order)), "Mark as Preparing")
        self.set_status(self.order, OrderStatus.READY)
        self.assertContains(self.client.get(self.detail_url(self.order)), "Record cash payment")
        self.set_status(self.order, OrderStatus.COMPLETED)
        content = self.client.get(self.detail_url(self.order)).content.decode()
        self.assertIsNone(re.search(r"Mark as|Record cash payment", content))


class SalesReportTests(OrderSetup, TestCase):
    def setUp(self):
        super().setUp()
        self.today = timezone.localdate()
        # Paid and completed today
        self.paid = self.place(quantities={self.adobo.pk: 2})
        self.set_status(self.paid, OrderStatus.READY)
        services.record_payment(self.paid, self.staff)
        self.set_status(self.paid, OrderStatus.COMPLETED)
        # Still pending and unpaid today
        self.place(student=self.other, quantities={self.adobo.pk: 1, self.tea.pk: 3})
        # Placed 10 days ago
        self.old = self.place(quantities={self.tea.pk: 10})
        Order.objects.filter(pk=self.old.pk).update(order_date=timezone.now() - timedelta(days=10))
        self.client.force_login(self.staff)

    def report(self, **params):
        return self.client.get(reverse("orders:sales_report"), params)

    def test_login_required(self):
        self.client.logout()
        url = reverse("orders:sales_report")
        self.assertRedirects(self.report(), f"{reverse('accounts:login')}?next={url}", fetch_redirect_response=False)

    def test_students_cannot_see_report(self):
        self.client.force_login(self.student)
        self.assertRedirects(self.report(), reverse("accounts:dashboard"), fetch_redirect_response=False)

    def test_staff_can_open_report_from_navbar(self):
        response = self.client.get(reverse("accounts:dashboard"), follow=True)
        self.assertContains(response, f'href="{reverse("orders:sales_report")}"')

    def test_default_is_last_seven_days(self):
        response = self.report()
        form = response.context["form"]
        self.assertEqual(form.cleaned_data["start"], self.today - timedelta(days=6))
        self.assertEqual(form.cleaned_data["end"], self.today)
        totals = response.context["report"]["totals"]
        self.assertEqual(totals["order_count"], 2)

    def test_counts_and_sales_only_include_paid_orders(self):
        response = self.report()
        report = response.context["report"]
        self.assertEqual(report["totals"], {
            "order_count": 2,
            "completed_count": 1,
            "sales": Decimal("130.00"),
        })
        self.assertEqual(report["daily"], [{
            "day": self.today,
            "order_count": 2,
            "completed_count": 1,
            "sales": Decimal("130.00"),
        }])
        self.assertContains(response, "&#8369;130.00")

    def test_most_ordered_item_per_category(self):
        top = self.report().context["report"]["top_items"]
        self.assertEqual(top, [
            {"category": "Drinks", "item": "Iced Tea", "quantity": 3},
            {"category": "Rice Meals", "item": "Chicken Adobo", "quantity": 3},
        ])

    def test_date_filter(self):
        old_day = self.today - timedelta(days=10)
        report = self.report(start=old_day, end=old_day).context["report"]
        self.assertEqual(report["totals"]["order_count"], 1)
        self.assertEqual(report["totals"]["sales"], Decimal("0"))
        self.assertEqual(report["top_items"], [{"category": "Drinks", "item": "Iced Tea", "quantity": 10}])

        # A wider range adds both days together
        report = self.report(start=old_day, end=self.today).context["report"]
        self.assertEqual(report["totals"]["order_count"], 3)
        self.assertEqual(len(report["daily"]), 2)
        self.assertEqual(report["top_items"][0]["quantity"], 13)

    def test_empty_range(self):
        response = self.report(start="2020-01-01", end="2020-01-31")
        self.assertEqual(response.context["report"]["totals"]["sales"], Decimal("0"))
        self.assertContains(response, "No orders in this date range.")
        self.assertContains(response, "No items were ordered in this date range.")

    def test_invalid_ranges_are_rejected(self):
        checks = [
            ({"start": self.today, "end": self.today - timedelta(days=1)},
             "The start date must be on or before the end date."),
            ({"start": self.today - timedelta(days=400), "end": self.today},
             "Choose a range of 366 days or less."),
            ({"start": "not-a-date", "end": self.today}, "Enter a valid date."),
            ({"start": "", "end": self.today}, "This field is required."),
        ]
        for params, error in checks:
            with self.subTest(params=params):
                response = self.report(**params)
                self.assertEqual(response.status_code, 200)
                self.assertIsNone(response.context["report"])
                self.assertContains(response, error)


class OrderAdminTests(OrderSetup, TestCase):
    def setUp(self):
        super().setUp()
        self.order = self.place()
        admin = User.objects.create_superuser(email="admin@cit.edu", password=PASSWORD, first_name="Ad", last_name="Min")
        self.client.force_login(admin)

    def test_orders_cannot_be_added_or_edited_in_admin(self):
        self.assertEqual(self.client.get("/admin/orders/order/add/").status_code, 403)
        response = self.client.get(f"/admin/orders/order/{self.order.pk}/change/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="_save"')
        self.assertContains(response, self.order.order_number)

    def test_orders_can_still_be_deleted_in_admin(self):
        response = self.client.post(f"/admin/orders/order/{self.order.pk}/delete/", {"post": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Order.objects.exists())
        self.assertFalse(Payment.objects.exists())
