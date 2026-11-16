from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


# Restrict a view to certain roles
def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            # Wrong role: send to own dashboard
            if request.user.role not in roles:
                return redirect('accounts:dashboard')
            return view_func(request, *args, **kwargs)

        # Login check runs first
        return login_required(_wrapped)

    return decorator
