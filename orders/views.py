from django.shortcuts import render

from accounts.decorators import role_required
from accounts.models import User

from .models import Order, OrderStatus

student_only = role_required(User.Role.STUDENT)
staff_only = role_required(User.Role.STAFF)


# Staff see every order, students only their own
def visible_orders(user):
    orders = Order.objects.select_related("user", "payment")
    if user.is_canteen_staff:
        return orders
    return orders.filter(user=user)


@student_only
def my_orders(request):
    orders = visible_orders(request.user)
    return render(request, "orders/my_orders.html", {
        "current": [order for order in orders if order.status != OrderStatus.COMPLETED],
        "history": [order for order in orders if order.status == OrderStatus.COMPLETED],
    })


@staff_only
def staff_orders(request):
    orders = visible_orders(request.user)
    return render(request, "orders/staff_orders.html", {"orders": orders})
