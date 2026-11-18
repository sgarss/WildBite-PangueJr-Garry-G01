from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import MenuItem, Order, OrderItem

User = get_user_model()
PASSWORD = 'Wildbite#2026x'


def make_user(email, role=User.Role.STUDENT):
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        first_name='Test',
        last_name='User',
        role=role,
    )


class OrderingFlowTests(TestCase):
    def setUp(self):
        self.student = make_user('student@cit.edu')
        self.other_student = make_user('other@cit.edu')
        self.staff = make_user('staff@cit.edu', User.Role.STAFF)
        self.rice = MenuItem.objects.create(
            name='Chicken Rice',
            category='Meals',
            price=Decimal('2.50'),
            created_by=self.staff,
        )
        self.juice = MenuItem.objects.create(
            name='Calamansi Juice',
            category='Drinks',
            price=Decimal('1.25'),
            created_by=self.staff,
        )

    def create_order(self, user=None, status=Order.Status.PENDING):
        order = Order.objects.create(user=user or self.student, status=status)
        OrderItem.objects.create(
            order=order,
            menu_item=self.rice,
            quantity=1,
            unit_price=self.rice.price,
        )
        order.total_amount = self.rice.price
        order.save(update_fields=('total_amount',))
        return order

    def test_student_places_order_with_multiple_items_and_saved_total(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse('orders:menu'), {
            f'quantity_{self.rice.pk}': '2',
            f'quantity_{self.juice.pk}': '1',
        })

        order = Order.objects.get(user=self.student)
        self.assertRedirects(response, reverse('orders:detail', args=(order.pk,)))
        self.assertEqual(order.total_amount, Decimal('6.25'))
        self.assertEqual(order.items.count(), 2)

    def test_order_requires_a_valid_nonzero_quantity(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse('orders:menu'), {
            f'quantity_{self.rice.pk}': '0',
            f'quantity_{self.juice.pk}': '100',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.exists())
        self.assertContains(response, 'Ensure this value is less than or equal to 99.')

    def test_order_requires_at_least_one_selected_item(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse('orders:menu'), {
            f'quantity_{self.rice.pk}': '0',
            f'quantity_{self.juice.pk}': '0',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Choose at least one menu item.')
        self.assertFalse(Order.objects.exists())

    def test_students_only_see_their_orders_and_staff_can_read_all_orders(self):
        order = self.create_order(user=self.other_student)
        self.client.force_login(self.student)

        self.assertNotContains(self.client.get(reverse('orders:my_orders')), f'Order #{order.pk}')
        self.assertEqual(
            self.client.get(reverse('orders:detail', args=(order.pk,))).status_code,
            404,
        )

        self.client.force_login(self.staff)
        self.assertEqual(
            self.client.get(reverse('orders:detail', args=(order.pk,))).status_code,
            200,
        )
        self.assertContains(self.client.get(reverse('orders:staff_orders')), f'Order #{order.pk}')

    def test_student_can_edit_and_delete_only_a_pending_order(self):
        order = self.create_order()
        self.client.force_login(self.student)
        response = self.client.post(reverse('orders:edit', args=(order.pk,)), {
            f'quantity_{self.rice.pk}': '3',
            f'quantity_{self.juice.pk}': '0',
        })

        self.assertRedirects(response, reverse('orders:detail', args=(order.pk,)))
        order.refresh_from_db()
        self.assertEqual(order.total_amount, Decimal('7.50'))
        self.assertEqual(order.items.get().quantity, 3)

        response = self.client.post(reverse('orders:delete', args=(order.pk,)))
        self.assertRedirects(response, reverse('orders:my_orders'))
        self.assertFalse(Order.objects.filter(pk=order.pk).exists())

    def test_staff_manage_menu_and_advance_orders_only_to_next_status(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse('orders:create_menu_item'), {
            'name': 'Soup',
            'description': 'Daily soup',
            'category': 'Meals',
            'price': '1.75',
            'is_available': 'on',
        })

        soup = MenuItem.objects.get(name='Soup')
        self.assertRedirects(response, reverse('orders:staff_menu'))
        self.assertEqual(soup.created_by, self.staff)

        response = self.client.post(reverse('orders:edit_menu_item', args=(soup.pk,)), {
            'name': 'Soup of the Day',
            'description': 'Daily soup special',
            'category': 'Meals',
            'price': '2.00',
            'is_available': 'on',
        })
        self.assertRedirects(response, reverse('orders:staff_menu'))
        soup.refresh_from_db()
        self.assertEqual(soup.name, 'Soup of the Day')
        self.assertEqual(soup.price, Decimal('2.00'))

        response = self.client.post(reverse('orders:delete_menu_item', args=(soup.pk,)))
        self.assertRedirects(response, reverse('orders:staff_menu'))
        self.assertFalse(MenuItem.objects.filter(pk=soup.pk).exists())

        order = self.create_order()
        response = self.client.post(reverse('orders:update_status', args=(order.pk,)), {
            'status': Order.Status.ACCEPTED,
        })
        self.assertRedirects(response, reverse('orders:detail', args=(order.pk,)))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.ACCEPTED)

        self.client.post(reverse('orders:update_status', args=(order.pk,)), {
            'status': Order.Status.READY,
        })
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.ACCEPTED)

    def test_role_restrictions_and_ordered_menu_items_cannot_be_deleted(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse('orders:staff_menu')).status_code, 302)

        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse('orders:menu')).status_code, 302)
        self.create_order()
        response = self.client.post(reverse('orders:delete_menu_item', args=(self.rice.pk,)))
        self.assertRedirects(response, reverse('orders:staff_menu'))
        self.assertTrue(MenuItem.objects.filter(pk=self.rice.pk).exists())
