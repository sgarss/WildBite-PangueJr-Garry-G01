from django import forms
from django.contrib.auth.forms import (
    AdminUserCreationForm,
    AuthenticationForm,
    UserChangeForm,
    UserCreationForm,
    UsernameField,
)

from .models import User


# ---------------------------------------------------------------------------
# Public forms (used by WildBite pages)
# ---------------------------------------------------------------------------

class RegistrationForm(UserCreationForm):
    """Public sign-up form. ALWAYS creates a STUDENT account.

    There is deliberately no "role" field here, so nobody can sign
    themselves up as canteen staff. Staff accounts are created by a staff
    admin in Django admin (or with `createsuperuser`).

    password1/password2 come from UserCreationForm, which:
      - checks that both passwords match, and
      - runs every validator in settings.AUTH_PASSWORD_VALIDATORS.
    """

    class Meta:
        model = User
        fields = ("full_name", "email")
        labels = {"full_name": "Full name", "email": "Email"}
        widgets = {
            "full_name": forms.TextInput(attrs={"autocomplete": "name", "placeholder": "Juan Dela Cruz"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "you@cit.edu"}),
        }

    def clean_full_name(self):
        full_name = (self.cleaned_data.get("full_name") or "").strip()
        if not full_name:
            raise forms.ValidationError("Please enter your full name.")
        return full_name

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data.get("email"))
        # iexact = case-insensitive, so "Juan@CIT.edu" matches "juan@cit.edu" (BR-01)
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)  # also hashes the password
        user.role = User.Role.STUDENT      # never trust the browser for the role
        user.is_staff = False
        user.is_superuser = False
        if commit:
            user.save()
        return user


class EmailLoginForm(AuthenticationForm):
    """Django's login form, with the "username" box labelled Email.

    Django's form still calls the field "username" internally, because
    USERNAME_FIELD = 'email' on our User model tells it what to look up.
    """

    username = UsernameField(
        label="Email",
        widget=forms.EmailInput(attrs={"autofocus": True, "placeholder": "you@cit.edu"}),
    )

    # One generic message for every failure (wrong email, wrong password,
    # inactive account) so attackers can't learn which emails are registered.
    error_messages = {
        "invalid_login": "Invalid email or password.",
        "inactive": "Invalid email or password.",
    }


# ---------------------------------------------------------------------------
# Admin-only forms (used by Django admin at /admin/)
# Django's built-in admin forms expect a "username" field, so we point them
# at our custom User model, which logs in with email instead.
# ---------------------------------------------------------------------------

class AdminUserAddForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = ("email", "full_name", "role")


class AdminUserEditForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"
