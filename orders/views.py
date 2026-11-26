from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User
from menu.models import MenuItem

from . import services
from .forms import OrderFilterForm, OrderItemsForm, SalesReportForm
from .models import Order, OrderStatus
from .reports import sales_summary

student_only = role_required(User.Role.STUDENT)
staff_only = role_required(User.Role.STAFF)


# Staff see every order, students only their own
def visible_orders(user):
    orders = Order.objects.select_related("user", "payment")
    if user.is_canteen_staff:
        return orders
    return orders.filter(user=user)


@student_only
def place_order(request):
    menu_items = MenuItem.objects.filter(is_available=True).select_related("category")
    if request.method == "POST":
        form = OrderItemsForm(request.POST, menu_items=menu_items)
        if form.is_valid():
            try:
                order = services.place_order(request.user, form.quantities)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(
                    request,
                    f"Order {order} placed. Pay ₱{order.total_amount:,.2f} in cash when you pick it up.",
                )
                return redirect("orders:detail", pk=order.pk)
        messages.error(request, "Please fix the errors below.")
    else:
        form = OrderItemsForm(menu_items=menu_items)

    return render(request, "orders/order_form.html", {"form": form, "title": "Place an order"})


@student_only
def my_orders(request):
    orders = visible_orders(request.user)
    return render(request, "orders/my_orders.html", {
        "current": [order for order in orders if order.status != OrderStatus.COMPLETED],
        "history": [order for order in orders if order.status == OrderStatus.COMPLETED],
    })


# Another student's order gives a 404
@login_required
def order_detail(request, pk):
    order = get_object_or_404(visible_orders(request.user), pk=pk)
    return render(request, "orders/order_detail.html", {
        "order": order,
        "items": order.items.select_related("menu_item"),
        "history": order.status_history.select_related("changed_by"),
    })


@student_only
def edit_order(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    if not order.is_pending:
        messages.error(request, "Only pending orders can be changed.")
        return redirect("orders:detail", pk=order.pk)

    current = {line.menu_item_id: line.quantity for line in order.items.all()}
    # Keep items already in the order even if they became unavailable
    menu_items = MenuItem.objects.filter(Q(is_available=True) | Q(pk__in=current)).select_related("category")

    if request.method == "POST":
        form = OrderItemsForm(request.POST, menu_items=menu_items)
        if form.is_valid():
            try:
                order = services.update_order(order, form.quantities)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, f"Order {order} updated. New total: ₱{order.total_amount:,.2f}.")
                return redirect("orders:detail", pk=order.pk)
        messages.error(request, "Please fix the errors below.")
    else:
        form = OrderItemsForm(menu_items=menu_items, initial_quantities=current)

    return render(request, "orders/order_form.html", {
        "form": form,
        "order": order,
        "title": f"Edit order {order}",
    })


@student_only
@require_POST
def cancel_order(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    try:
        services.cancel_order(order)
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return redirect("orders:detail", pk=order.pk)
    messages.success(request, f"Order {order} was cancelled.")
    return redirect("orders:my_orders")


# Incoming orders with search and filters
@staff_only
def staff_orders(request):
    form = OrderFilterForm(request.GET)
    orders = visible_orders(request.user)

    if form.is_valid():
        query = form.cleaned_data["q"].strip()
        status = form.cleaned_data["status"]
        date = form.cleaned_data["date"]
        if query:
            orders = orders.filter(order_number__icontains=query)
        if status:
            orders = orders.filter(status=status)
        if date:
            orders = orders.filter(order_date__date=date)

    filtering = any(request.GET.get(key) for key in ("q", "status", "date"))
    return render(request, "orders/staff_orders.html", {
        "form": form,
        "orders": orders,
        "filtering": filtering,
    })


@staff_only
@require_POST
def advance_status(request, pk):
    order = get_object_or_404(Order, pk=pk)
    try:
        order = services.advance_status(order, request.user)
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(request, f"Order {order} is now {order.get_status_display()}.")
    return redirect("orders:detail", pk=pk)


@staff_only
@require_POST
def record_payment(request, pk):
    order = get_object_or_404(Order, pk=pk)
    try:
        payment = services.record_payment(order, request.user)
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(request, f"Cash payment of ₱{payment.amount:,.2f} recorded for order {order}.")
    return redirect("orders:detail", pk=pk)


# Orders and sales per day for a date range (last 7 days by default)
@staff_only
def sales_report(request):
    if "start" in request.GET or "end" in request.GET:
        data = request.GET
    else:
        today = timezone.localdate()
        data = {"start": today - timedelta(days=6), "end": today}
    form = SalesReportForm(data)

    report = None
    if form.is_valid():
        report = sales_summary(form.cleaned_data["start"], form.cleaned_data["end"])
    return render(request, "orders/sales_report.html", {"form": form, "report": report})
