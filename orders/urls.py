from django.urls import path

from . import views

app_name = 'orders'

urlpatterns = [
    path('menu/', views.menu, name='menu'),
    path('my/', views.my_orders, name='my_orders'),
    path('staff/', views.staff_orders, name='staff_orders'),
    path('staff/menu/', views.staff_menu, name='staff_menu'),
    path('staff/menu/new/', views.create_menu_item, name='create_menu_item'),
    path('staff/menu/<int:item_id>/edit/', views.edit_menu_item, name='edit_menu_item'),
    path('staff/menu/<int:item_id>/delete/', views.delete_menu_item, name='delete_menu_item'),
    path('<int:order_id>/', views.order_detail, name='detail'),
    path('<int:order_id>/edit/', views.edit_order, name='edit'),
    path('<int:order_id>/delete/', views.delete_order, name='delete'),
    path('<int:order_id>/status/', views.update_order_status, name='update_status'),
]
