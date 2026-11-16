import re

from django import forms
from django.contrib.auth.forms import (
    AdminUserCreationForm,
    AuthenticationForm,
    UserChangeForm,
    UserCreationForm,
    UsernameField,
)

from .models import User

MAX_PHOTO_SIZE = 2 * 1024 * 1024


# Trim a name and reject blanks
def clean_name(value, label):
    value = (value or "").strip()
    if not value:
        raise forms.ValidationError(f"Please enter your {label}.")
    return value


# Student sign-up form (no role field)
class RegistrationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        labels = {"first_name": "First name", "last_name": "Last name", "email": "Email"}
        widgets = {
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name", "placeholder": "Juan"}),
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name", "placeholder": "Dela Cruz"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "you@cit.edu"}),
        }

    def clean_first_name(self):
        return clean_name(self.cleaned_data.get("first_name"), "first name")

    def clean_last_name(self):
        return clean_name(self.cleaned_data.get("last_name"), "last name")

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
    remove_photo = forms.BooleanField(required=False, label="Remove current photo")

    class Meta:
        model = User
        # Only these fields are editable (never role or permissions)
        fields = ("first_name", "last_name", "email", "contact_number", "profile_photo")
        labels = {
            "first_name": "First name",
            "last_name": "Last name",
            "email": "Email",
            "contact_number": "Contact number",
            "profile_photo": "Profile photo",
        }
        help_texts = {
            "contact_number": "Optional. Example: 09171234567",
            "profile_photo": "JPG, PNG, GIF or WEBP, up to 2 MB. Leave empty to keep your current photo.",
        }
        widgets = {
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name"}),
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "contact_number": forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel", "placeholder": "09171234567"}),
            "profile_photo": forms.FileInput(attrs={"accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remember the current photo so it can be deleted after a change
        self.old_photo = self.instance.profile_photo.name or ""

    def clean_first_name(self):
        return clean_name(self.cleaned_data.get("first_name"), "first name")

    def clean_last_name(self):
        return clean_name(self.cleaned_data.get("last_name"), "last name")

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data.get("email"))
        # Unique email, skipping the user's own record
        taken = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists()
        if taken:
            raise forms.ValidationError("An account with this email already exists.")
        return email

    # Digits only, with an optional leading +
    def clean_contact_number(self):
        number = re.sub(r"[\s\-()]", "", self.cleaned_data.get("contact_number") or "")
        if number and not re.fullmatch(r"\+?\d{7,15}", number):
            raise forms.ValidationError("Enter a valid contact number, e.g. 09171234567.")
        return number

    # Size limit for new uploads
    def clean_profile_photo(self):
        photo = self.cleaned_data.get("profile_photo")
        upload = self.files.get(self.add_prefix("profile_photo"))
        if upload and upload.size > MAX_PHOTO_SIZE:
            raise forms.ValidationError("Photo must be 2 MB or smaller.")
        return photo

    def save(self, commit=True):
        user = super().save(commit=False)
        new_upload = self.files.get(self.add_prefix("profile_photo"))
        # Remove photo only when no new one was uploaded
        if self.cleaned_data.get("remove_photo") and not new_upload:
            user.profile_photo = ""
        if commit:
            user.save()
            # Delete the old file once it's replaced or removed
            if self.old_photo and user.profile_photo.name != self.old_photo:
                user.profile_photo.storage.delete(self.old_photo)
        return user


# Django admin forms for the custom user
class AdminUserAddForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "role")


class AdminUserEditForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"
