from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    """Allow a view only for users whose role is in `roles`.

    Usage:
        @role_required('STAFF')
        def staff_dashboard(request): ...

    1. Not logged in?  -> login_required sends them to the login page with ?next=
    2. Wrong role?     -> PermissionDenied, which Django shows as templates/403.html
    3. Right role?     -> the view runs normally
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if request.user.role not in roles:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        # login_required runs FIRST, so request.user is always a real user above
        return login_required(_wrapped)

    return decorator
