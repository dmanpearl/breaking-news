import hashlib
import secrets

from django.conf import settings
from django.db import models


def _generate_key():
    """Return a new random API key string (plaintext, shown once on creation)."""
    return secrets.token_urlsafe(32)


def _hash_key(key: str) -> str:
    """SHA-256 hash of the key. Only the hash is stored in the DB."""
    return hashlib.sha256(key.encode()).hexdigest()


class APIKey(models.Model):
    """
    A bearer token granting read-only access to the Breaking News API.

    The plaintext key is generated once and never stored. Only the SHA-256
    hash is persisted. The key is shown to the admin exactly once at creation
    time via the Django admin interface.
    """

    label = models.CharField(
        max_length=120,
        help_text="Human-readable name for this key (e.g. 'Acme Corp integration').",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="api_keys",
        help_text="Optional — link this key to a Breaking News user account.",
    )
    key_hash = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
        help_text="SHA-256 hash of the bearer token. The plaintext is never stored.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Deactivate to revoke access without deleting the record.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Updated on each authenticated request.",
    )

    class Meta:
        verbose_name = "API Key"
        verbose_name_plural = "API Keys"
        ordering = ["-created_at"]

    def __str__(self):
        status = "active" if self.is_active else "revoked"
        return f"{self.label} ({status})"

    @classmethod
    def create_key(cls, label: str, owner=None) -> tuple["APIKey", str]:
        """
        Create a new APIKey and return (instance, plaintext_key).
        The plaintext key is returned exactly once and must be shown to
        the user immediately — it cannot be recovered later.
        """
        plaintext = _generate_key()
        instance = cls.objects.create(
            label=label,
            owner=owner,
            key_hash=_hash_key(plaintext),
        )
        return instance, plaintext

    @classmethod
    def authenticate(cls, plaintext: str) -> "APIKey | None":
        """
        Look up an active key by its plaintext value.
        Returns the APIKey instance or None if invalid/inactive.
        Updates last_used_at on success.
        """
        from django.utils import timezone

        h = _hash_key(plaintext)
        try:
            key = cls.objects.get(key_hash=h, is_active=True)
        except cls.DoesNotExist:
            return None
        key.last_used_at = timezone.now()
        key.save(update_fields=["last_used_at"])
        return key
