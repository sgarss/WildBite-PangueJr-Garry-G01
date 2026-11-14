from django.urls import path

from wildbite.views import coming_soon

from . import views

app_name = 'accounts'

urlpatterns = [
    path('accounts/register/', views.register, name='register'),

    # TEMPORARY: these names exist so the navbar links work.
    # Each one is replaced with the real view in its own phase.
    path('accounts/login/', coming_soon, {'title': 'Login'}, name='login'),                   # Phase 5
    path('accounts/logout/', coming_soon, {'title': 'Logout'}, name='logout'),                # Phase 5
    path('dashboard/', coming_soon, {'title': 'Dashboard'}, name='dashboard'),                # Phase 6
    path('accounts/profile/', coming_soon, {'title': 'Profile'}, name='profile'),             # Phase 7
]
