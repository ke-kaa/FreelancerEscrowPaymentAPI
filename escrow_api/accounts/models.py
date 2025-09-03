from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager, PermissionsMixin, UserManager
from country_list import countries_for_language
from auditlog.registry import auditlog
from auditlog.models import AuditlogHistoryField


class CustomUserManager(BaseUserManager):
    """
    Manager for CustomUser. Handles user and superuser creation using email as the unique identifier.
    """
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        return self.create_user(email, password, **extra_fields)


class ActiveUserManager(UserManager):
    """
    Manager for active users only (is_active=True, deleted_at=None).
    """
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True, deleted_at__isnull=True)
    

class CustomUser(AbstractUser):
    """
    Custom user model for the platform.
    Uses email as the unique identifier and supports 'freelancer' and 'client' user types.
    Includes audit logging and soft deletion (deleted_at).
    """
    USER_TYPE_CHOICES = (
        ('freelancer', 'Freelancer'),
        ('client', 'Client'),
    )

    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES)
    phone_number = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=50, choices=countries_for_language('en'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    email = models.EmailField(unique=True, blank=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    username = None

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name',]

    objects = CustomUserManager()
    active_objects = ActiveUserManager()

    history = AuditlogHistoryField()

    def __str__(self):
        return self.email
    

auditlog.register(CustomUser, exclude_fields=[])