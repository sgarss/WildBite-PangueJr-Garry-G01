from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    # Auth
    path('accounts/register/', views.register, name='register'),
    path('accounts/login/', views.WildBiteLoginView.as_view(), name='login'),
    path('accounts/logout/', views.WildBiteLogoutView.as_view(), name='logout'),

    # Dashboards
    path('dashboard/', views.dashboard, name='dashboard'),
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('staff/dashboard/', views.staff_dashboard, name='staff_dashboard'),

    # Profile and password
    path('accounts/profile/', views.profile, name='profile'),
    path('accounts/profile/edit/', views.profile_edit, name='profile_edit'),
    path('accounts/password/change/', views.WildBitePasswordChangeView.as_view(), name='password_change'),
    path('accounts/password/change/done/', views.WildBitePasswordChangeDoneView.as_view(), name='password_change_done'),
]
