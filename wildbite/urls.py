from django.contrib import admin
from django.urls import include, path

from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    # Placeholder page for features that are not built yet (menu, orders, ...)
    path('coming-soon/<slug:feature>/', views.coming_soon, name='coming_soon'),
    # Account pages: /accounts/..., /dashboard/, /student/..., /staff/...
    path('', include('accounts.urls')),
]
