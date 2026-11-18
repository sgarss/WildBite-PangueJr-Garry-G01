from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Now
from django.utils import timezone

from menu.models import MenuItem


class OrderStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PREPARING = "PREPARING", "Preparing"
    READY = "READY", "Ready for pickup"
    COMPLETED = "COMPLETED", "Completed"


# Orders move forward one step at a time
NEXT_STATUS = {
    OrderStatus.PENDING: OrderStatus.PREPARING,
    OrderStatus.PREPARING: OrderStatus.READY,
    OrderStatus.READY: OrderStatus.COMPLETED,
}


class Order(models.Model):
    Status = OrderStatus

    order_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
        db_column="user_id",
    )
    order_number = models.CharField(max_length=20, unique=True)
    order_date = models.DateTimeField(default=timezone.now, db_default=Now())
    status = models.CharField(
        max_length=15,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
        db_default=OrderStatus.PENDING,
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "orders"
        ordering = ["-order_date", "-order_id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=OrderStatus.values),
                name="orders_status_check",
            ),
            models.CheckConstraint(
                condition=Q(total_amount__gte=0),
                name="orders_total_amount_check",
            ),
        ]

    def __str__(self):
        return self.order_number

    @property
    def is_pending(self):
        return self.status == OrderStatus.PENDING

    @property
    def next_status(self):
        return NEXT_STATUS.get(self.status)


class OrderItem(models.Model):
    order_item_id = models.AutoField(primary_key=True)
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        db_column="order_id",
    )
    # Items used in an order can't be deleted
    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.RESTRICT,
        related_name="order_items",
        db_column="menu_item_id",
    )
    quantity = models.IntegerField()
    # Price at the time of ordering
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "order_items"
        ordering = ["order_item_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "menu_item"],
                name="order_items_order_menu_item_key",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gte=1),
                name="order_items_quantity_check",
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gt=0),
                name="order_items_unit_price_check",
            ),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.menu_item}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity


class OrderStatusHistory(models.Model):
    history_id = models.AutoField(primary_key=True)
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="status_history",
        db_column="order_id",
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="status_changes",
        db_column="changed_by",
    )
    status = models.CharField(max_length=15, choices=OrderStatus.choices)
    changed_at = models.DateTimeField(default=timezone.now, db_default=Now())

    class Meta:
        db_table = "order_status_history"
        ordering = ["changed_at", "history_id"]
        verbose_name_plural = "order status history"
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=OrderStatus.values),
                name="order_status_history_status_check",
            ),
        ]

    def __str__(self):
        return f"{self.order} - {self.get_status_display()}"


class Payment(models.Model):
    class Status(models.TextChoices):
        UNPAID = "UNPAID", "Unpaid"
        PAID = "PAID", "Paid"

    payment_id = models.AutoField(primary_key=True)
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="payment",
        db_column="order_id",
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payments_received",
        db_column="received_by",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.UNPAID,
        db_default=Status.UNPAID,
    )
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payments"
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gte=0),
                name="payments_amount_check",
            ),
            models.CheckConstraint(
                condition=Q(payment_status__in=["UNPAID", "PAID"]),
                name="payments_payment_status_check",
            ),
            # paid_at is set only when the payment is PAID
            models.CheckConstraint(
                condition=(
                    Q(payment_status="PAID", paid_at__isnull=False)
                    | Q(payment_status="UNPAID", paid_at__isnull=True)
                ),
                name="payments_paid_at_check",
            ),
        ]

    def __str__(self):
        return f"{self.order} - {self.get_payment_status_display()}"

    @property
    def is_paid(self):
        return self.payment_status == self.Status.PAID
