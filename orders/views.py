from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User

from .forms import MenuItemForm, OrderSelectionForm, OrderStatusForm
from .models import MenuItem, Order, OrderItem


def _order_queryset(user):
    orders = Order.objects.prefetch_related('items__menu_item', 'user')
    if user.role != User.Role.STAFF:
        orders = orders.filter(user=user)
    return orders


def _menu_items_for_order(existing_quantities=None):
    query = Q(is_available=True)
    if existing_quantities:
        query |= Q(pk__in=existing_quantities)
    return MenuItem.objects.filter(query).order_by('category', 'name')


def _save_order_items(order, quantities):
    with transaction.atomic():
        locked_order = Order.objects.select_for_update().get(pk=order.pk)
        current_items = {
            item.menu_item_id: item
            for item in locked_order.items.select_for_update().all()
        }
        locked_menu_items = {}

        for menu_item, quantity in quantities.items():
            locked_item = MenuItem.objects.select_for_update().get(pk=menu_item.pk)
            locked_menu_items[locked_item.pk] = locked_item
            old_item = current_items.get(locked_item.pk)
            if not locked_item.is_available and (
                old_item is None or quantity > old_item.quantity
            ):
                raise ValidationError(f'{locked_item.name} is no longer available.')

        for menu_item_id, order_item in current_items.items():
            if not any(item.pk == menu_item_id for item in quantities):
                order_item.delete()

        for menu_item, quantity in quantities.items():
            old_item = current_items.get(menu_item.pk)
            if old_item:
                old_item.quantity = quantity
                old_item.save(update_fields=('quantity',))
            else:
                OrderItem.objects.create(
                    order=locked_order,
                    menu_item=locked_menu_items[menu_item.pk],
                    quantity=quantity,
                    unit_price=locked_menu_items[menu_item.pk].price,
                )

        locked_order.total_amount = sum(
            (item.line_total for item in locked_order.items.all()),
            Decimal('0.00'),
        )
        locked_order.save(update_fields=('total_amount', 'updated_at'))


@role_required(User.Role.STUDENT)
def menu(request):
    menu_items = MenuItem.objects.filter(is_available=True)
    form = OrderSelectionForm(request.POST or None, menu_items=menu_items)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                order = Order.objects.create(user=request.user)
                _save_order_items(order, form.selected_quantities)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, f'Order #{order.pk} placed successfully.')
            return redirect('orders:detail', order_id=order.pk)
    return render(request, 'orders/menu.html', {'menu_items': menu_items, 'form': form})


@role_required(User.Role.STUDENT)
def my_orders(request):
    return render(request, 'orders/order_list.html', {
        'orders': _order_queryset(request.user),
        'staff_view': False,
    })


@role_required(User.Role.STAFF)
def staff_orders(request):
    return render(request, 'orders/order_list.html', {
        'orders': _order_queryset(request.user),
        'staff_view': True,
    })


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(_order_queryset(request.user), pk=order_id)
    status_form = OrderStatusForm(order=order) if request.user.role == User.Role.STAFF else None
    return render(request, 'orders/order_detail.html', {
        'order': order,
        'status_form': status_form,
    })


@role_required(User.Role.STUDENT)
def edit_order(request, order_id):
    order = get_object_or_404(Order.objects.filter(user=request.user), pk=order_id)
    if order.status != Order.Status.PENDING:
        messages.error(request, 'Only pending orders can be edited.')
        return redirect('orders:detail', order_id=order.pk)

    existing_quantities = {
        item.menu_item_id: item.quantity for item in order.items.all()
    }
    menu_items = _menu_items_for_order(existing_quantities)
    form = OrderSelectionForm(
        request.POST or None,
        menu_items=menu_items,
        existing_quantities=existing_quantities,
    )
    if request.method == 'POST' and form.is_valid():
        try:
            _save_order_items(order, form.selected_quantities)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, f'Order #{order.pk} updated successfully.')
            return redirect('orders:detail', order_id=order.pk)
    return render(request, 'orders/order_form.html', {
        'order': order,
        'form': form,
        'menu_items': menu_items,
        'editing': True,
    })


@role_required(User.Role.STUDENT)
@require_POST
def delete_order(request, order_id):
    order = get_object_or_404(Order.objects.filter(user=request.user), pk=order_id)
    if order.status != Order.Status.PENDING:
        messages.error(request, 'Only pending orders can be deleted.')
    else:
        order.delete()
        messages.success(request, 'Your pending order was deleted.')
    return redirect('orders:my_orders')


@role_required(User.Role.STAFF)
def staff_menu(request):
    return render(request, 'orders/staff_menu.html', {'menu_items': MenuItem.objects.all()})


@role_required(User.Role.STAFF)
def create_menu_item(request):
    form = MenuItemForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        menu_item = form.save(commit=False)
        menu_item.created_by = request.user
        menu_item.save()
        messages.success(request, f'{menu_item.name} was added to the menu.')
        return redirect('orders:staff_menu')
    return render(request, 'orders/menu_item_form.html', {'form': form, 'title': 'Add menu item'})


@role_required(User.Role.STAFF)
def edit_menu_item(request, item_id):
    menu_item = get_object_or_404(MenuItem, pk=item_id)
    form = MenuItemForm(request.POST or None, instance=menu_item)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'{menu_item.name} was updated.')
        return redirect('orders:staff_menu')
    return render(request, 'orders/menu_item_form.html', {
        'form': form,
        'title': f'Edit {menu_item.name}',
    })


@role_required(User.Role.STAFF)
def delete_menu_item(request, item_id):
    menu_item = get_object_or_404(MenuItem, pk=item_id)
    if request.method == 'POST':
        try:
            menu_item.delete()
        except ProtectedError:
            messages.error(
                request,
                'This menu item is part of an order and cannot be deleted. You can mark it unavailable instead.',
            )
        else:
            messages.success(request, f'{menu_item.name} was deleted.')
        return redirect('orders:staff_menu')
    return render(request, 'orders/menu_item_confirm_delete.html', {'menu_item': menu_item})


@role_required(User.Role.STAFF)
@require_POST
def update_order_status(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    form = OrderStatusForm(request.POST, order=order)
    if form.is_valid() and form.cleaned_data.get('status'):
        order.status = form.cleaned_data['status']
        order.save(update_fields=('status', 'updated_at'))
        messages.success(request, f'Order #{order.pk} status updated to {order.get_status_display()}.')
    else:
        messages.error(request, 'That status change is not allowed for this order.')
    return redirect('orders:detail', order_id=order.pk)
