from django.urls import path

from wildbite.views import coming_soon

from . import views

app_name = 'accounts'

urlpatterns = [
    path('accounts/register/', views.register, name='register'),
    path('accounts/login/', views.WildBiteLoginView.as_view(), name='login'),
    path('accounts/logout/', views.WildBiteLogoutView.as_view(), name='logout'),

    # TEMPORARY: these names exist so the navbar links work.
    # Each one is replaced with the real view in its own phase.
    path('dashboard/', coming_soon, {'title': 'Dashboard'}, name='dashboard'),                # Phase 6
    path('accounts/profile/', coming_soon, {'title': 'Profile'}, name='profile'),             # Phase 7
]
