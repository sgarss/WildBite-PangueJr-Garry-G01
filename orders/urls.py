from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("", views.my_orders, name="my_orders"),
    path("new/", views.place_order, name="place"),
    path("staff/", views.staff_orders, name="staff_orders"),
    path("reports/", views.sales_report, name="sales_report"),
    path("<int:pk>/", views.order_detail, name="detail"),
    path("<int:pk>/edit/", views.edit_order, name="edit"),
    path("<int:pk>/cancel/", views.cancel_order, name="cancel"),
    path("<int:pk>/status/", views.advance_status, name="advance_status"),
    path("<int:pk>/payment/", views.record_payment, name="record_payment"),
]
