from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("", views.my_orders, name="my_orders"),
    path("staff/", views.staff_orders, name="staff_orders"),
]
