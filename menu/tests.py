from decimal import Decimal

from django.db import IntegrityError, connection, transaction
from django.db.models import RestrictedError
from django.test import TestCase
from django.urls import reverse

from accounts.tests import make_staff, make_student

from .models import Category, MenuItem


def make_item(category, name="Chicken Adobo", price="65.00", available=True):
    return MenuItem.objects.create(
        category=category, name=name, price=Decimal(price), is_available=available
    )


class MenuModelTests(TestCase):
    def setUp(self):
        self.rice = Category.objects.create(name="Rice Meals")

    def test_tables_match_sdd(self):
        self.assertEqual(Category._meta.db_table, "categories")
        self.assertEqual(MenuItem._meta.db_table, "menu_items")

    def test_category_name_must_be_unique(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Category.objects.create(name="Rice Meals")

    def test_menu_item_name_must_be_unique(self):
        make_item(self.rice)
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_item(self.rice)

    def test_database_rejects_zero_price(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_item(self.rice, price="0.00")

    def test_new_item_is_available_by_default(self):
        item = MenuItem.objects.create(category=self.rice, name="Lumpia", price=Decimal("20"))
        self.assertTrue(item.is_available)

    def test_category_with_items_cannot_be_deleted(self):
        make_item(self.rice)
        with self.assertRaises(RestrictedError):
            self.rice.delete()

    def test_database_foreign_key_is_on_delete_restrict(self):
        make_item(self.rice)
        with self.assertRaises(IntegrityError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM categories WHERE category_id = %s", [self.rice.pk])


class MenuAccessTests(TestCase):
    def setUp(self):
        self.student = make_student()
        self.staff = make_staff()
        self.rice = Category.objects.create(name="Rice Meals")
        self.item = make_item(self.rice)

    def test_anonymous_redirected_to_login(self):
        for name in ["menu:list", "menu:item_add", "menu:category_list"]:
            with self.subTest(url=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response["Location"].startswith(reverse("accounts:login")))

    def test_student_can_view_menu_without_staff_actions(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("menu:list"))
        self.assertContains(response, "Chicken Adobo")
        self.assertContains(response, "&#8369;65.00")
        self.assertNotContains(response, reverse("menu:item_add"))
        self.assertNotContains(response, reverse("menu:item_edit", args=[self.item.pk]))

    def test_staff_sees_management_actions(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("menu:list"))
        self.assertContains(response, reverse("menu:item_add"))
        self.assertContains(response, reverse("menu:item_edit", args=[self.item.pk]))

    def test_student_cannot_use_staff_pages(self):
        self.client.force_login(self.student)
        pages = [
            ("get", reverse("menu:item_add")),
            ("get", reverse("menu:item_edit", args=[self.item.pk])),
            ("post", reverse("menu:item_delete", args=[self.item.pk])),
            ("post", reverse("menu:item_toggle", args=[self.item.pk])),
            ("get", reverse("menu:category_list")),
            ("get", reverse("menu:category_add")),
            ("post", reverse("menu:category_delete", args=[self.rice.pk])),
        ]
        for method, url in pages:
            with self.subTest(url=url):
                response = getattr(self.client, method)(url)
                self.assertRedirects(response, reverse("accounts:dashboard"), fetch_redirect_response=False)

        self.item.refresh_from_db()
        self.assertTrue(self.item.is_available)
        self.assertTrue(Category.objects.filter(pk=self.rice.pk).exists())


class CategoryManagementTests(TestCase):
    def setUp(self):
        self.client.force_login(make_staff())
        self.rice = Category.objects.create(name="Rice Meals")

    def test_add_category(self):
        response = self.client.post(
            reverse("menu:category_add"), {"name": " Drinks ", "description": ""}, follow=True
        )
        self.assertRedirects(response, reverse("menu:category_list"))
        self.assertContains(response, "Category added.")
        drinks = Category.objects.get(name="Drinks")
        self.assertIsNone(drinks.description)

    def test_duplicate_category_rejected_in_any_case(self):
        response = self.client.post(reverse("menu:category_add"), {"name": "rice meals"})
        self.assertContains(response, "A category with this name already exists.")
        self.assertEqual(Category.objects.count(), 1)

    def test_blank_category_name_rejected(self):
        response = self.client.post(reverse("menu:category_add"), {"name": "   "})
        self.assertContains(response, "This field is required.")

    def test_edit_category(self):
        self.client.post(
            reverse("menu:category_edit", args=[self.rice.pk]),
            {"name": "Rice Meals", "description": "Meals with rice"},
        )
        self.rice.refresh_from_db()
        self.assertEqual(self.rice.description, "Meals with rice")

    def test_delete_empty_category(self):
        response = self.client.post(reverse("menu:category_delete", args=[self.rice.pk]), follow=True)
        self.assertContains(response, "Rice Meals was deleted.")
        self.assertFalse(Category.objects.exists())

    def test_cannot_delete_category_with_items(self):
        make_item(self.rice)
        response = self.client.post(reverse("menu:category_delete", args=[self.rice.pk]), follow=True)
        self.assertContains(response, "still has menu items")
        self.assertTrue(Category.objects.filter(pk=self.rice.pk).exists())


class MenuItemManagementTests(TestCase):
    def setUp(self):
        self.client.force_login(make_staff())
        self.rice = Category.objects.create(name="Rice Meals")

    def item_data(self, **overrides):
        data = {
            "category": self.rice.pk,
            "name": "Pork Sisig",
            "description": "",
            "price": "75.50",
            "is_available": "on",
        }
        data.update(overrides)
        return data

    def test_add_menu_item(self):
        response = self.client.post(reverse("menu:item_add"), self.item_data(), follow=True)
        self.assertRedirects(response, reverse("menu:list"))
        self.assertContains(response, "Pork Sisig was added to the menu.")
        item = MenuItem.objects.get(name="Pork Sisig")
        self.assertEqual(item.price, Decimal("75.50"))
        self.assertEqual(item.category, self.rice)
        self.assertTrue(item.is_available)

    def test_price_must_be_greater_than_zero(self):
        for price in ["0", "-5"]:
            with self.subTest(price=price):
                response = self.client.post(reverse("menu:item_add"), self.item_data(price=price))
                self.assertContains(response, "Price must be greater than zero.")
        self.assertFalse(MenuItem.objects.exists())

    def test_invalid_price_rejected(self):
        response = self.client.post(reverse("menu:item_add"), self.item_data(price="abc"))
        self.assertContains(response, "Enter a number.")

    def test_category_required(self):
        response = self.client.post(reverse("menu:item_add"), self.item_data(category=""))
        self.assertContains(response, "Please choose a category.")

    def test_duplicate_item_name_rejected_in_any_case(self):
        make_item(self.rice, name="Pork Sisig")
        response = self.client.post(reverse("menu:item_add"), self.item_data(name="PORK SISIG"))
        self.assertContains(response, "A menu item with this name already exists.")

    def test_add_item_needs_a_category_first(self):
        Category.objects.all().delete()
        response = self.client.get(reverse("menu:item_add"))
        self.assertRedirects(response, reverse("menu:category_add"), fetch_redirect_response=False)

    def test_edit_menu_item(self):
        item = make_item(self.rice)
        self.client.post(
            reverse("menu:item_edit", args=[item.pk]),
            self.item_data(name="Chicken Adobo", price="70.00"),
        )
        item.refresh_from_db()
        self.assertEqual(item.price, Decimal("70.00"))

    def test_toggle_availability(self):
        item = make_item(self.rice)
        url = reverse("menu:item_toggle", args=[item.pk])
        response = self.client.post(url, follow=True)
        self.assertContains(response, "Chicken Adobo is now unavailable.")
        item.refresh_from_db()
        self.assertFalse(item.is_available)

        self.client.post(url)
        item.refresh_from_db()
        self.assertTrue(item.is_available)

        self.assertEqual(self.client.get(url).status_code, 405)

    def test_delete_menu_item(self):
        item = make_item(self.rice)
        response = self.client.post(reverse("menu:item_delete", args=[item.pk]), follow=True)
        self.assertContains(response, "Chicken Adobo was deleted.")
        self.assertFalse(MenuItem.objects.exists())


class MenuSearchTests(TestCase):
    def setUp(self):
        self.client.force_login(make_student())
        rice = Category.objects.create(name="Rice Meals")
        drinks = Category.objects.create(name="Drinks")
        make_item(rice, name="Chicken Adobo")
        make_item(rice, name="Pork Adobo", available=False)
        make_item(drinks, name="Iced Tea", price="25.00")
        self.drinks = drinks

    def get_menu(self, **params):
        return self.client.get(reverse("menu:list"), params)

    def test_search_by_name(self):
        response = self.get_menu(q="adobo")
        self.assertContains(response, "Chicken Adobo")
        self.assertContains(response, "Pork Adobo")
        self.assertNotContains(response, "Iced Tea")

    def test_filter_by_category(self):
        response = self.get_menu(category=self.drinks.pk)
        self.assertContains(response, "Iced Tea")
        self.assertNotContains(response, "Chicken Adobo")

    def test_filter_by_availability(self):
        response = self.get_menu(availability="available")
        self.assertContains(response, "Chicken Adobo")
        self.assertNotContains(response, "Pork Adobo")

        response = self.get_menu(availability="unavailable")
        self.assertContains(response, "Pork Adobo")
        self.assertNotContains(response, "Chicken Adobo")

    def test_no_results_message(self):
        response = self.get_menu(q="pizza")
        self.assertContains(response, "No menu items match your search.")

    def test_invalid_filter_shows_error(self):
        response = self.get_menu(category=99999)
        self.assertContains(response, "Select a valid choice.")
        self.assertContains(response, "No menu items match your search.")
        self.assertNotContains(response, "Chicken Adobo")
