from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField


class BNUserManager(UserManager):
    """
    Overrides email normalization so that a blank or missing email is stored
    as NULL instead of an empty string. This prevents UNIQUE constraint
    violations when multiple users are created without an email address.
    Django's built-in AbstractUserManager.normalize_email() converts '' to ''
    which is not NULL, causing the second blank-email user to fail.
    """

    @classmethod
    def normalize_email(cls, email):
        normalized = super().normalize_email(email)
        return normalized if normalized else None

    def _create_user(self, username, email, password, **extra_fields):
        email = self.normalize_email(email)
        return super()._create_user(username, email, password, **extra_fields)


class User(AbstractUser):
    objects = BNUserManager()
    email = models.EmailField(unique=True, blank=True, null=True, default=None)
    phone = PhoneNumberField(blank=True)
    bio = models.TextField(blank=True)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        ordering = ["username"]

    def __str__(self):
        return f"{self.get_full_name()} ({self.username})"


class SiteSettings(models.Model):
    headline_enable = models.BooleanField(
        default=False,
        help_text="Show the Headline field in the message editor.",
    )
    inactivity_timeout_mins = models.PositiveIntegerField(
        default=15, help_text="Minutes of inactivity before auto-logout."
    )
    inactivity_warning_secs = models.PositiveIntegerField(
        default=45,
        help_text="Seconds before timeout to show the warning dialog.",
    )

    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"

    def __str__(self):
        return "Site Settings"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # prevent deletion
