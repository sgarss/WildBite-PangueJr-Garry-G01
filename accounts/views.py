from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeDoneView,
    PasswordChangeView,
)
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy

from .decorators import role_required
from .forms import EmailLoginForm, ProfileForm, RegistrationForm
from .models import ProfilePhoto, User


def register(request):
    # Already logged in
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            # Create student account
            form.save()
            messages.success(request, 'Account created successfully. Please log in.')
            return redirect('accounts:login')
        messages.error(request, 'Please fix the errors below.')
    else:
        form = RegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


# Check login credentials (Django LoginView)
class WildBiteLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = EmailLoginForm
    # Skip login page if already logged in
    redirect_authenticated_user = True


# End session (POST only)
class WildBiteLogoutView(LogoutView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.info(request, 'You have been logged out.')
        return response


# Redirect by role
@login_required
def dashboard(request):
    if request.user.role == User.Role.STAFF:
        return redirect('accounts:staff_dashboard')
    if request.user.role == User.Role.STUDENT:
        return redirect('accounts:student_dashboard')
    raise PermissionDenied


# Students only
@role_required(User.Role.STUDENT)
def student_dashboard(request):
    return render(request, 'accounts/student_dashboard.html')


# Canteen staff only
@role_required(User.Role.STAFF)
def staff_dashboard(request):
    return render(request, 'accounts/staff_dashboard.html')


# Own profile only (request.user)
@login_required
def profile(request):
    return render(request, 'accounts/profile.html', {'profile_user': request.user})


@login_required
def profile_edit(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            # Save profile changes
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('accounts:profile')
        messages.error(request, 'Please fix the errors below.')
    else:
        form = ProfileForm(instance=request.user)

    return render(request, 'accounts/profile_edit.html', {'form': form})


# Serve only the logged-in user's own photo (no user ID in the URL)
@login_required
def profile_photo(request):
    photo = get_object_or_404(ProfilePhoto, user=request.user)
    response = HttpResponse(bytes(photo.image), content_type=photo.content_type)
    response['Cache-Control'] = 'private'
    return response


# Change password, stays logged in
class WildBitePasswordChangeView(PasswordChangeView):
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('accounts:password_change_done')


class WildBitePasswordChangeDoneView(PasswordChangeDoneView):
    template_name = 'accounts/password_change_done.html'
