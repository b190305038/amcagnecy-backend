from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


# Roles mirror the frontend `Role` union in src/lib/auth.tsx. These are also
# the exact values of Employee.designation (core/models.py) — designation
# *is* the system role; there is no separate role vocabulary anymore.
class Role(models.TextChoices):
    MANAGER = "Manager", "Manager"
    DSM = "DSM", "Divisional Sales Manager"
    ASM = "ASM", "Area Sales Manager"
    ASE = "ASE", "Area Sales Executive"
    SE = "SE", "Sales Executive"
    SUPPORT_STAFF = "Support Staff", "Support Staff"
    ADMINISTRATIVE = "Administrative", "Administrative"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", Role.MANAGER)
        if extra.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """Email-authenticated user. Fields mirror the frontend `AppUser` shape."""

    name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    id_number = models.CharField(max_length=40, blank=True, default="")
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.SE)
    branch = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(max_length=20, default="Active")  # Active | Inactive

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} <{self.email}>"
