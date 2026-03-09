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
        on_delete=models.CASCADE,
        related_name="api_keys",
        help_text=(
            "The Breaking News user account that owns this key. "
            "Deactivating or deleting the user will revoke the key."
        ),
    )
    allowed_origins = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text=(
            "Comma-separated list of permitted origins "
            "(e.g. reader.breakingnewsguys.com, localhost:8080). "
            "Leave blank to allow any origin."
        ),
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
    def create_key(cls, label: str, owner, allowed_origins: str = "") -> tuple["APIKey", str]:
        """
        Create a new APIKey and return (instance, plaintext_key).
        The plaintext key is returned exactly once and must be shown to
        the user immediately — it cannot be recovered later.
        owner is required — every key must be associated with a user.
        """
        plaintext = _generate_key()
        instance = cls.objects.create(
            label=label,
            owner=owner,
            allowed_origins=allowed_origins,
            key_hash=_hash_key(plaintext),
        )
        return instance, plaintext

    def _get_request_origin(self, request) -> str:
        """
        Extract the best available origin identifier from the request.
        Prefers the HTTP Origin header (set by browsers for cross-origin
        requests), falls back to Referer hostname, then empty string.
        """
        origin = request.META.get("HTTP_ORIGIN", "").strip()
        if origin:
            # Strip scheme: "https://reader.breakingnewsguys.com" → "reader.breakingnewsguys.com"
            for scheme in ("https://", "http://"):
                if origin.startswith(scheme):
                    origin = origin[len(scheme):]
            return origin.rstrip("/")

        referer = request.META.get("HTTP_REFERER", "").strip()
        if referer:
            # Strip scheme and path: "https://reader.example.com/page" → "reader.example.com"
            for scheme in ("https://", "http://"):
                if referer.startswith(scheme):
                    referer = referer[len(scheme):]
            return referer.split("/")[0]

        return ""

    def check_origin(self, request) -> tuple[bool, str]:
        """
        Validate the request origin against this key's allowed_origins list.
        Returns (allowed: bool, detected_origin: str).
        If allowed_origins is blank, all origins are permitted.
        """
        if not self.allowed_origins.strip():
            return True, ""

        detected = self._get_request_origin(request)
        allowed = [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

        for entry in allowed:
            # Allow exact match or subdomain match
            if detected == entry or detected.endswith("." + entry):
                return True, detected

        return False, detected

    @classmethod
    def authenticate(cls, plaintext: str, request=None) -> "APIKey | None | tuple":
        """
        Look up an active key by its plaintext value.

        Returns:
          - APIKey instance on success
          - None if the key is invalid or inactive
          - tuple ("origin_rejected", detected_origin) if the key is valid but
            the request origin is not in the key's allowed_origins list

        Also rejects if the key's owner account is inactive.
        Updates last_used_at and appends an APIKeyUsage log row on success.
        """
        from django.utils import timezone

        h = _hash_key(plaintext)
        try:
            key = cls.objects.select_related("owner").get(key_hash=h, is_active=True)
        except cls.DoesNotExist:
            return None

        # Reject if the owning user account has been deactivated.
        if not key.owner.is_active:
            return None

        # Check origin restriction if the key has one and a request is present.
        if request is not None:
            allowed, detected = key.check_origin(request)
            if not allowed:
                return ("origin_rejected", detected)

        now = timezone.now()
        key.last_used_at = now
        key.save(update_fields=["last_used_at"])
        APIKeyUsage.log(key, request)
        return key


# Maps request paths to human-friendly endpoint labels.
_ENDPOINT_LABELS = {
    "/api/v1/stream": "Stream",
    "/api/v1/messages/latest": "Latest Message",
    "/api/v1/messages": "Messages",
    "/api/v1/health": "Health",
    "/api/v1/docs": "Docs",
    "/api/v1/redoc": "Redoc",
}


def _endpoint_label(path: str) -> str:
    """Return a friendly label for a request path, falling back to the raw path."""
    if not path:
        return ""
    # Exact match first
    if path in _ENDPOINT_LABELS:
        return _ENDPOINT_LABELS[path]
    # Prefix match for /api/v1/messages/{id}
    for prefix, label in _ENDPOINT_LABELS.items():
        if path.startswith(prefix + "/"):
            return label
    return path


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
    endpoint = models.CharField(
        max_length=200,
        blank=True,
        default="",
        db_index=True,
        help_text="Request path, e.g. /api/v1/stream",
    )
    referer = models.CharField(
        max_length=300,
        blank=True,
        default="",
        help_text="HTTP Referer header, indicates the calling origin.",
    )

    class Meta:
        verbose_name = "API Key Usage"
        verbose_name_plural = "API Key Usage"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.api_key.label} @ {self.timestamp:%Y-%m-%d %H:%M:%S}"

    @property
    def endpoint_label(self) -> str:
        return _endpoint_label(self.endpoint)

    @classmethod
    def log(cls, api_key: APIKey, request=None) -> None:
        """Create a usage log row. Silently no-ops if anything goes wrong."""
        try:
            ip = None
            ua = ""
            endpoint = ""
            referer = ""
            if request is not None:
                forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
                ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")
                ua = request.META.get("HTTP_USER_AGENT", "")[:300]
                endpoint = (request.path or "")[:200]
                referer = request.META.get("HTTP_REFERER", "")[:300]
            cls.objects.create(
                api_key=api_key,
                ip_address=ip or None,
                user_agent=ua,
                endpoint=endpoint,
                referer=referer,
            )
        except Exception:
            pass
