from django.urls import path

from wildbite.views import coming_soon

from . import views

app_name = 'accounts'

urlpatterns = [
    path('accounts/register/', views.register, name='register'),
    path('accounts/login/', views.WildBiteLoginView.as_view(), name='login'),
    path('accounts/logout/', views.WildBiteLogoutView.as_view(), name='logout'),

    path('dashboard/', views.dashboard, name='dashboard'),
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('staff/dashboard/', views.staff_dashboard, name='staff_dashboard'),

    # TEMPORARY: this name exists so the navbar link works (replaced in Phase 7).
    path('accounts/profile/', coming_soon, {'title': 'Profile'}, name='profile'),
]
