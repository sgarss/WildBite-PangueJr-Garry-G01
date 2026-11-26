import re

from django import forms
from django.contrib.auth.forms import (
    AdminUserCreationForm,
    AuthenticationForm,
    UserChangeForm,
    UserCreationForm,
    UsernameField,
)
from django.db import transaction
from django.utils import timezone

from .models import ProfilePhoto, User

MAX_PHOTO_SIZE = 2 * 1024 * 1024

# Allowed image formats (as detected by Pillow) and their content types
PHOTO_TYPES = {
    "JPEG": ProfilePhoto.ContentType.JPEG,
    "PNG": ProfilePhoto.ContentType.PNG,
    "GIF": ProfilePhoto.ContentType.GIF,
    "WEBP": ProfilePhoto.ContentType.WEBP,
}


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
    # Pillow checks that the upload is a real image
    profile_photo = forms.ImageField(
        required=False,
        label="Profile photo",
        help_text="JPG, PNG, GIF or WEBP, up to 2 MB. Leave empty to keep your current photo.",
        widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/gif,image/webp"}),
    )
    remove_photo = forms.BooleanField(required=False, label="Remove current photo")

    class Meta:
        model = User
        # Only these fields are editable (never role or permissions)
        fields = ("first_name", "last_name", "email", "contact_number")
        labels = {
            "first_name": "First name",
            "last_name": "Last name",
            "email": "Email",
            "contact_number": "Contact number",
        }
        help_texts = {
            "contact_number": "Optional. Example: 09171234567",
        }
        widgets = {
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name"}),
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "contact_number": forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel", "placeholder": "09171234567"}),
        }

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

    # Size and format checks (format comes from the image itself, not the file name)
    def clean_profile_photo(self):
        photo = self.cleaned_data.get("profile_photo")
        if not photo:
            return None
        if photo.size > MAX_PHOTO_SIZE:
            raise forms.ValidationError("Photo must be 2 MB or smaller.")
        if photo.image.format not in PHOTO_TYPES:
            raise forms.ValidationError("Only JPG, PNG, GIF or WEBP photos are allowed.")
        return photo

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            # User details and photo are saved together or not at all
            with transaction.atomic():
                user.save()
                self.save_photo(user)
        return user

    def save_photo(self, user):
        photo = self.cleaned_data.get("profile_photo")
        if photo:
            photo.seek(0)
            now = timezone.now()
            ProfilePhoto.objects.update_or_create(
                user=user,
                defaults={
                    "image": photo.read(),
                    "content_type": PHOTO_TYPES[photo.image.format],
                    "uploaded_at": now,
                },
            )
            user.photo_uploaded_at = now
        elif self.cleaned_data.get("remove_photo"):
            ProfilePhoto.objects.filter(user=user).delete()
            user.photo_uploaded_at = None
        else:
            return
        user.save(update_fields=["photo_uploaded_at"])


# Django admin forms for the custom user
class AdminUserAddForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "role")


class AdminUserEditForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"
