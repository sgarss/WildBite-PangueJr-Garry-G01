from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models import Q
from django.db.models.functions import Now
from django.utils import timezone


class UserManager(BaseUserManager):
    """Creates users. Django calls this from createsuperuser, forms, tests, etc."""

    use_in_migrations = True

    @classmethod
    def normalize_email(cls, email):
        # Store the WHOLE email in lowercase (Django's default only lowercases
        # the domain part). This makes "Juan@CIT.edu" and "juan@cit.edu" the same.
        return (email or "").strip().lower()

    def get_by_natural_key(self, username):
        # Used during login: lets a user log in even if they type capitals.
        return self.get(**{self.model.USERNAME_FIELD: self.normalize_email(username)})

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)  # hashes the password, never stores plain text
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.STUDENT)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

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


class User(AbstractBaseUser, PermissionsMixin):
    """WildBite user. Maps to the `users` table in the SDD."""

    class Role(models.TextChoices):
        STUDENT = "STUDENT", "Student"
        STAFF = "STAFF", "Staff"

    user_id = models.AutoField(primary_key=True)
    email = models.EmailField(max_length=100, unique=True)
    # Same field Django already has, renamed in the database to match the SDD.
    # It holds a HASH such as "pbkdf2_sha256$...", never the real password.
    password = models.CharField("password", max_length=255, db_column="password_hash")
    full_name = models.CharField(max_length=100)
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.STUDENT,
        db_default=Role.STUDENT,  # DEFAULT 'STUDENT' at the database level too
    )
    created_at = models.DateTimeField(default=timezone.now, db_default=Now())

    # Required by Django admin / auth:
    # is_active = can log in at all.
    # is_staff  = can open the Django admin site (/admin/). NOT the same as role STAFF.
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]  # asked by createsuperuser (email + password are always asked)

    class Meta:
        db_table = "users"
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

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_canteen_staff(self):
        return self.role == self.Role.STAFF
