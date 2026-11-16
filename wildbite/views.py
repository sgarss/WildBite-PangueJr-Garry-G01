from django.shortcuts import redirect, render


def home(request):
    # Logged-in users go to their dashboard
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    return render(request, 'home.html')


# Placeholder for features not built yet
def coming_soon(request, feature):
    title = feature.replace('-', ' ').title()
    return render(request, 'coming_soon.html', {'title': title})
