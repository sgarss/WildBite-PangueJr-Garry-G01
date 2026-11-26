from django.contrib import admin

from .models import Order, OrderItem, OrderStatusHistory, Payment


# Orders are changed only through the site, so the order rules always apply
class ViewOnlyInline:
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class OrderItemInline(ViewOnlyInline, admin.TabularInline):
    model = OrderItem


class StatusHistoryInline(ViewOnlyInline, admin.TabularInline):
    model = OrderStatusHistory


class PaymentInline(ViewOnlyInline, admin.StackedInline):
    model = Payment


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "user", "status", "total_amount", "order_date")
    list_filter = ("status", "order_date")
    search_fields = ("order_number", "user__email")
    inlines = (OrderItemInline, StatusHistoryInline, PaymentInline)

    # Admins can view and delete orders, but not add or edit them
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
