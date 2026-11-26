from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate

from .models import Order, OrderItem, OrderStatus, Payment

# Sales only count cash that was actually received
PAID = Q(payment__payment_status=Payment.Status.PAID)
COMPLETED = Q(status=OrderStatus.COMPLETED)


def sales_summary(start, end):
    orders = Order.objects.filter(order_date__date__range=(start, end))
    counts = {
        "order_count": Count("pk"),
        "completed_count": Count("pk", filter=COMPLETED),
        "sales": Sum("payment__amount", filter=PAID, default=Decimal("0")),
    }

    daily = (
        orders.annotate(day=TruncDate("order_date"))
        .values("day")
        .annotate(**counts)
        .order_by("day")
    )

    item_totals = (
        OrderItem.objects.filter(order__order_date__date__range=(start, end))
        .values("menu_item__category__name", "menu_item__name")
        .annotate(quantity=Sum("quantity"))
        .order_by("menu_item__category__name", "-quantity", "menu_item__name")
    )
    # Rows are sorted by quantity, so the first one per category is the top item
    top_items = {}
    for row in item_totals:
        top_items.setdefault(row["menu_item__category__name"], {
            "category": row["menu_item__category__name"],
            "item": row["menu_item__name"],
            "quantity": row["quantity"],
        })

    return {
        "totals": orders.aggregate(**counts),
        "daily": list(daily),
        "top_items": list(top_items.values()),
    }
