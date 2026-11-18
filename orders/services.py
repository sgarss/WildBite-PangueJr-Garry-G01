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
