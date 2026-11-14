"""Site-wide pages that do not belong to one specific app."""
from django.contrib import messages
from django.shortcuts import redirect, render


def home(request):
    """Homepage at "/". Logged-in users go straight to their dashboard."""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    return render(request, 'home.html')


def coming_soon(request, feature='', title=None):
    """Temporary page for features that are not built yet."""
    title = title or feature.replace('-', ' ').title() or 'This page'
    messages.info(request, f'{title} is coming soon.')
    return render(request, 'coming_soon.html', {'title': title})
