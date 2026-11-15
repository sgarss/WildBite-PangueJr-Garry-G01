from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


# Restrict a view to certain roles
def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            # Check user role
            if request.user.role not in roles:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        # Login check runs first
        return login_required(_wrapped)

    return decorator
