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
    def authenticate(cls, plaintext: str, request=None) -> "APIKey | None":
        """
        Look up an active key by its plaintext value.
        Returns the APIKey instance or None if invalid/inactive.
        Updates last_used_at and appends an APIKeyUsage log row on success.
        """
        from django.utils import timezone

        h = _hash_key(plaintext)
        try:
            key = cls.objects.get(key_hash=h, is_active=True)
        except cls.DoesNotExist:
            return None
        now = timezone.now()
        key.last_used_at = now
        key.save(update_fields=["last_used_at"])
        APIKeyUsage.log(key, request)
        return key


class APIKeyUsage(models.Model):
    """
    Append-only log of successful API key authentications.
    Rows older than 120 days are pruned by the prune_api_usage management command.
    """

    api_key = models.ForeignKey(
        APIKey,
        on_delete=models.CASCADE,
        related_name="usage_logs",
    )
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        verbose_name = "API Key Usage"
        verbose_name_plural = "API Key Usage"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.api_key.label} @ {self.timestamp:%Y-%m-%d %H:%M:%S}"

    @classmethod
    def log(cls, api_key: APIKey, request=None) -> None:
        """Create a usage log row. Silently no-ops if anything goes wrong."""
        try:
            ip = None
            ua = ""
            if request is not None:
                forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
                ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")
                ua = request.META.get("HTTP_USER_AGENT", "")[:300]
            cls.objects.create(api_key=api_key, ip_address=ip or None, user_agent=ua)
        except Exception:
            pass
