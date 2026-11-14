from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render

from .forms import EmailLoginForm, RegistrationForm


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
