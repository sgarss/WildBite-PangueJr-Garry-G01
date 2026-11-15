from django import forms
from django.contrib.auth.forms import (
    AdminUserCreationForm,
    AuthenticationForm,
    UserChangeForm,
    UserCreationForm,
    UsernameField,
)

from .models import User


# Student sign-up form (no role field)
class RegistrationForm(UserCreationForm):
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

    # Check unique email (any letter case)
    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data.get("email"))
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        # Always register as student
        user.role = User.Role.STUDENT
        user.is_staff = False
        user.is_superuser = False
        if commit:
            user.save()
        return user


# Login form with email
class EmailLoginForm(AuthenticationForm):
    username = UsernameField(
        label="Email",
        widget=forms.EmailInput(attrs={"autofocus": True, "placeholder": "you@cit.edu"}),
    )

    # Same message for any failed login
    error_messages = {
        "invalid_login": "Invalid email or password.",
        "inactive": "Invalid email or password.",
    }


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        # Only name and email are editable
        fields = ("full_name", "email")
        labels = {"full_name": "Full name", "email": "Email"}
        widgets = {
            "full_name": forms.TextInput(attrs={"autocomplete": "name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
        }

    def clean_full_name(self):
        full_name = (self.cleaned_data.get("full_name") or "").strip()
        if not full_name:
            raise forms.ValidationError("Please enter your full name.")
        return full_name

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data.get("email"))
        # Unique email, skipping the user's own record
        taken = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists()
        if taken:
            raise forms.ValidationError("An account with this email already exists.")
        return email


# Django admin forms for the custom user
class AdminUserAddForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = ("email", "full_name", "role")


class AdminUserEditForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"
