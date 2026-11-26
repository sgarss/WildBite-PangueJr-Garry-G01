from django.contrib import admin
from django.urls import include, path

from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    # Account pages
    path('', include('accounts.urls')),
    path('menu/', include('menu.urls')),
    path('orders/', include('orders.urls')),
]
