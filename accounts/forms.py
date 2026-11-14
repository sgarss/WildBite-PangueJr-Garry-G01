from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from .models import User


# Forms used ONLY by the Django admin site (/admin/).
# Django's built-in admin forms expect a "username" field, so we point them
# at our custom User model, which logs in with email instead.

class AdminUserAddForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = ("email", "full_name", "role")


class AdminUserEditForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"
