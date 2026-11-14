from django.urls import path

from wildbite.views import coming_soon

app_name = 'accounts'

# TEMPORARY: these names exist so the navbar links work.
# Each one is replaced with the real view in its own phase.
urlpatterns = [
    path('accounts/register/', coming_soon, {'title': 'Registration'}, name='register'),      # Phase 4
    path('accounts/login/', coming_soon, {'title': 'Login'}, name='login'),                   # Phase 5
    path('accounts/logout/', coming_soon, {'title': 'Logout'}, name='logout'),                # Phase 5
    path('dashboard/', coming_soon, {'title': 'Dashboard'}, name='dashboard'),                # Phase 6
    path('accounts/profile/', coming_soon, {'title': 'Profile'}, name='profile'),             # Phase 7
]
