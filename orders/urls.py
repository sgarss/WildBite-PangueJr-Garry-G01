from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("", views.my_orders, name="my_orders"),
    path("new/", views.place_order, name="place"),
    path("staff/", views.staff_orders, name="staff_orders"),
    path("<int:pk>/", views.order_detail, name="detail"),
    path("<int:pk>/edit/", views.edit_order, name="edit"),
    path("<int:pk>/cancel/", views.cancel_order, name="cancel"),
]
