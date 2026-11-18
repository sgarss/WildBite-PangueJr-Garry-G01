from django.contrib import admin

from .models import Order, OrderItem, OrderStatusHistory, Payment


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


class StatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ("changed_at",)


class PaymentInline(admin.StackedInline):
    model = Payment
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "user", "status", "total_amount", "order_date")
    list_filter = ("status", "order_date")
    search_fields = ("order_number", "user__email")
    readonly_fields = ("order_date",)
    inlines = (OrderItemInline, StatusHistoryInline, PaymentInline)
