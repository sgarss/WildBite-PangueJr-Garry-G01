from django.contrib import admin
from django.urls import include, path

from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('coming-soon/<slug:feature>/', views.coming_soon, name='coming_soon'),
    # Account pages
    path('', include('accounts.urls')),
]
