from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeDoneView,
    PasswordChangeView,
)
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .decorators import role_required
from .forms import EmailLoginForm, ProfileForm, RegistrationForm
from .models import User


def register(request):
    """Public sign-up page: /accounts/register/ (always creates a STUDENT)."""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account created successfully. Please log in.')
            return redirect('accounts:login')
        messages.error(request, 'Please fix the errors below.')
    else:
        form = RegistrationForm()

    # On errors, the same form object is shown again: typed values stay,
    # passwords are cleared (Django never re-displays password inputs).
    return render(request, 'accounts/register.html', {'form': form})


class WildBiteLoginView(LoginView):
    """/accounts/login/ using Django's built-in LoginView.

    Django already handles the hard parts for us:
      - checks the email + hashed password,
      - starts a new session (and changes the session ID, to stop session fixation),
      - follows ?next=... ONLY if it points to our own site (blocks redirects to other sites),
      - otherwise sends the user to LOGIN_REDIRECT_URL (accounts:dashboard).
    """

    template_name = 'accounts/login.html'
    authentication_form = EmailLoginForm
    redirect_authenticated_user = True  # already logged in? go to the dashboard


class WildBiteLogoutView(LogoutView):
    """/accounts/logout/ (POST only in Django 5). Ends the session, then
    redirects to LOGOUT_REDIRECT_URL (the login page)."""

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.info(request, 'You have been logged out.')
        return response


# ---------------------------------------------------------------------------
# Dashboards (BR-18: staff pages must reject students, and vice versa)
# ---------------------------------------------------------------------------

@login_required
def dashboard(request):
    """/dashboard/ - sends each user to the dashboard for their role."""
    if request.user.role == User.Role.STAFF:
        return redirect('accounts:staff_dashboard')
    if request.user.role == User.Role.STUDENT:
        return redirect('accounts:student_dashboard')
    raise PermissionDenied  # unknown role (the CHECK constraint should prevent this)


@role_required(User.Role.STUDENT)
def student_dashboard(request):
    return render(request, 'accounts/student_dashboard.html')


@role_required(User.Role.STAFF)
def staff_dashboard(request):
    return render(request, 'accounts/staff_dashboard.html')


# ---------------------------------------------------------------------------
# Profile
# These views ALWAYS use request.user (the logged-in person). There is no
# user ID in the URL, so nobody can open or edit someone else's profile.
# ---------------------------------------------------------------------------

@login_required
def profile(request):
    """/accounts/profile/ - shows the logged-in user's own details."""
    return render(request, 'accounts/profile.html', {'profile_user': request.user})


@login_required
def profile_edit(request):
    """/accounts/profile/edit/ - edit own full name and email only."""
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('accounts:profile')
        messages.error(request, 'Please fix the errors below.')
    else:
        form = ProfileForm(instance=request.user)

    return render(request, 'accounts/profile_edit.html', {'form': form})


class WildBitePasswordChangeView(PasswordChangeView):
    """/accounts/password/change/ (login required by Django).

    Django's PasswordChangeView asks for the old password, checks the new one
    against AUTH_PASSWORD_VALIDATORS, hashes it, and updates the session so
    the user STAYS logged in after the change.
    """

    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('accounts:password_change_done')


class WildBitePasswordChangeDoneView(PasswordChangeDoneView):
    template_name = 'accounts/password_change_done.html'
