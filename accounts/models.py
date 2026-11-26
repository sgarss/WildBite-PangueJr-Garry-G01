import uuid
from pathlib import Path

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models import Q
from django.db.models.functions import Now
from django.utils import timezone


# Only used by old migrations (photos are now stored in the database)
def profile_photo_path(instance, filename):
    return f"profile_photos/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


class UserManager(BaseUserManager):
    use_in_migrations = True

    # Store emails in lowercase
    @classmethod
    def normalize_email(cls, email):
        return (email or "").strip().lower()

    # Case-insensitive email lookup on login
    def get_by_natural_key(self, username):
        return self.get(**{self.model.USERNAME_FIELD: self.normalize_email(username)})

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        # Hash password
        user.set_password(password)
        user.save(using=self._db)
        return user

    # New users are students by default
    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.STUDENT)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    # Admin account (STAFF role + Django admin access)
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.STAFF)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("role") != User.Role.STAFF:
            raise ValueError("Superuser must have role=STAFF.")
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


# Custom user (users table)
class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        STUDENT = "STUDENT", "Student"
        STAFF = "STAFF", "Staff"

    user_id = models.AutoField(primary_key=True)
    email = models.EmailField(max_length=100, unique=True)
    # Hashed password, saved as password_hash
    password = models.CharField("password", max_length=255, db_column="password_hash")
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    contact_number = models.CharField(max_length=20, blank=True, default="")
    # Set when the user has a photo; also used to refresh the cached image
    photo_uploaded_at = models.DateTimeField(null=True, blank=True, editable=False)
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.STUDENT,
        db_default=Role.STUDENT,
    )
    created_at = models.DateTimeField(default=timezone.now, db_default=Now())

    # is_staff = Django admin access, not the STAFF role
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    # Log in with email
    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        db_table = "users"
        # Role must be STUDENT or STAFF
        constraints = [
            models.CheckConstraint(
                condition=Q(role__in=["STUDENT", "STAFF"]),
                name="users_role_check",
            ),
        ]

    def __str__(self):
        return self.email

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email)

    # First + last name for greetings and display
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.first_name

    # Role checks
    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_canteen_staff(self):
        return self.role == self.Role.STAFF


# Profile photo bytes, kept apart from users so pages don't load the image
class ProfilePhoto(models.Model):
    class ContentType(models.TextChoices):
        JPEG = "image/jpeg", "JPEG"
        PNG = "image/png", "PNG"
        GIF = "image/gif", "GIF"
        WEBP = "image/webp", "WEBP"

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="photo",
        db_column="user_id",
    )
    image = models.BinaryField()
    content_type = models.CharField(max_length=20, choices=ContentType.choices)
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "profile_photos"
        constraints = [
            models.CheckConstraint(
                condition=Q(content_type__in=["image/jpeg", "image/png", "image/gif", "image/webp"]),
                name="profile_photos_content_type_check",
            ),
        ]

    def __str__(self):
        return f"Photo of {self.user}"
