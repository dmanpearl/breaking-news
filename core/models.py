from django.contrib.auth.models import AbstractUser
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField


class User(AbstractUser):
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
