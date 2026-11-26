from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from menu.models import MenuItem

from .models import Order, OrderItem, OrderStatus, OrderStatusHistory, Payment


# Order numbers look like WB-261118-001 (date + count for that day)
def next_order_number():
    prefix = timezone.localdate().strftime("WB-%y%m%d-")
    numbers = Order.objects.filter(order_number__startswith=prefix).values_list("order_number", flat=True)
    last = max((int(number[len(prefix):]) for number in numbers), default=0)
    return f"{prefix}{last + 1:03d}"


# Lock the chosen menu items so price and availability can't change mid-order
def locked_menu_items(quantities):
    items = MenuItem.objects.select_for_update().filter(pk__in=quantities)
    found = {item.pk: item for item in items}
    if len(found) != len(quantities):
        raise ValidationError("Some items are no longer on the menu. Please check your order.")
    return found


def create_order(student, total):
    # Two orders at the same moment can get the same number, so try again
    for attempt in range(5):
        try:
            with transaction.atomic():
                return Order.objects.create(
                    user=student,
                    order_number=next_order_number(),
                    total_amount=total,
                )
        except IntegrityError:
            if attempt == 4:
                raise


@transaction.atomic
def place_order(student, quantities):
    if not quantities:
        raise ValidationError("Choose at least one menu item.")

    items = locked_menu_items(quantities)
    unavailable = [item.name for item in items.values() if not item.is_available]
    if unavailable:
        raise ValidationError(f"No longer available: {', '.join(unavailable)}.")

    total = sum((items[pk].price * qty for pk, qty in quantities.items()), Decimal("0.00"))
    order = create_order(student, total)
    OrderItem.objects.bulk_create([
        OrderItem(order=order, menu_item=items[pk], quantity=qty, unit_price=items[pk].price)
        for pk, qty in quantities.items()
    ])
    # New orders start as PENDING and UNPAID
    OrderStatusHistory.objects.create(order=order, changed_by=student, status=OrderStatus.PENDING)
    Payment.objects.create(order=order, amount=total)
    return order


def locked_pending_order(order, action):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if not order.is_pending:
        raise ValidationError(f"Only pending orders can be {action}.")
    return order


@transaction.atomic
def update_order(order, quantities):
    order = locked_pending_order(order, "changed")
    if not quantities:
        raise ValidationError("Choose at least one menu item. To remove everything, cancel the order.")

    lines = {line.menu_item_id: line for line in order.items.all()}
    items = locked_menu_items(quantities)
    # Unavailable items can stay in the order but can't be added or increased
    blocked = [
        item.name for pk, item in items.items()
        if not item.is_available and quantities[pk] > (lines[pk].quantity if pk in lines else 0)
    ]
    if blocked:
        raise ValidationError(f"No longer available: {', '.join(blocked)}.")

    for pk, line in lines.items():
        if pk not in quantities:
            line.delete()
    for pk, qty in quantities.items():
        if pk in lines:
            lines[pk].quantity = qty
            lines[pk].save(update_fields=["quantity"])
        else:
            OrderItem.objects.create(order=order, menu_item=items[pk], quantity=qty, unit_price=items[pk].price)

    order.total_amount = sum((line.line_total for line in order.items.all()), Decimal("0.00"))
    order.save(update_fields=["total_amount"])
    Payment.objects.filter(order=order).update(amount=order.total_amount)
    return order


# Move the order one step forward and record who did it
@transaction.atomic
def advance_status(order, staff, current_status=None):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if current_status is not None and order.status != current_status:
        raise ValidationError(f"This order was already moved to {order.get_status_display()}. Nothing was changed.")
    new_status = order.next_status
    if new_status is None:
        raise ValidationError("This order is already completed.")
    if new_status == OrderStatus.COMPLETED and not order.payment.is_paid:
        raise ValidationError("Record the cash payment before completing this order.")

    order.status = new_status
    order.save(update_fields=["status"])
    OrderStatusHistory.objects.create(order=order, changed_by=staff, status=new_status)
    return order


# Cash is paid when the student picks up a ready order
@transaction.atomic
def record_payment(order, staff):
    order = Order.objects.select_for_update().get(pk=order.pk)
    payment = order.payment
    if payment.is_paid:
        raise ValidationError("This order is already paid.")
    if order.status != OrderStatus.READY:
        raise ValidationError("Cash can be recorded once the order is ready for pickup.")

    payment.payment_status = Payment.Status.PAID
    payment.amount = order.total_amount
    payment.paid_at = timezone.now()
    payment.received_by = staff
    payment.save()
    return payment


# Cancelling deletes the order with its items, history and payment
@transaction.atomic
def cancel_order(order):
    locked_pending_order(order, "cancelled").delete()
