from django.contrib import messages
from django.shortcuts import redirect, render

from .forms import RegistrationForm


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
