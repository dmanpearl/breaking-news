import hmac
import hashlib
import time

from django.conf import settings
from django.contrib import admin
from django.http import Http404
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.html import format_html

from .models import APIKey, APIKeyUsage

# ---------------------------------------------------------------------------
# One-time signed token helpers
# ---------------------------------------------------------------------------
# When a key is created we embed the plaintext in a short-lived HMAC-signed
# token in the redirect URL.  The change_view verifies and consumes the token,
# passing the plaintext to the template as extra_context so a modal can render
# it.  Nothing is stored in the session or the database.
#
# Token format (query param ?_key_token=<ts>.<plaintext>.<sig>):
#   ts        — unix timestamp (int), token expires after TOKEN_TTL seconds
#   plaintext — the raw key string (URL-safe base64, no dots)
#   sig       — HMAC-SHA256(SECRET_KEY, f"{ts}.{plaintext}")
#
# TTL is intentionally short — just long enough to survive the redirect.
# ---------------------------------------------------------------------------

TOKEN_TTL = 120  # seconds


def _make_token(plaintext: str) -> str:
    ts = str(int(time.time()))
    msg = f"{ts}.{plaintext}"
    sig = hmac.new(
        settings.SECRET_KEY.encode(),
        msg.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{ts}.{plaintext}.{sig}"


def _verify_token(token: str) -> str | None:
    """
    Verify a token and return the plaintext if valid, else None.
    Tokens are valid for TOKEN_TTL seconds from creation.
    """
    try:
        ts_str, plaintext, sig = token.split(".", 2)
    except ValueError:
        return None

    # Check expiry
    try:
        if int(time.time()) - int(ts_str) > TOKEN_TTL:
            return None
    except ValueError:
        return None

    # Verify signature
    msg = f"{ts_str}.{plaintext}"
    expected = hmac.new(
        settings.SECRET_KEY.encode(),
        msg.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None

    return plaintext


# ---------------------------------------------------------------------------
# APIKey admin
# ---------------------------------------------------------------------------


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = (
        "label",
        "owner",
        "is_active",
        "created_at",
        "last_used_at",
    )
    list_display_links = ("label",)
    list_editable = ("is_active",)
    list_filter = ("is_active",)
    readonly_fields = ("key_hash", "created_at", "last_used_at", "plaintext_notice")
    fields = (
        "label",
        "owner",
        "allowed_origins",
        "is_active",
        "plaintext_notice",
        "key_hash",
        "created_at",
        "last_used_at",
    )
    search_fields = ("label", "owner__username", "owner__email")

    def get_fields(self, request, obj=None):
        if obj is None:
            return ("label", "owner", "allowed_origins")
        return super().get_fields(request, obj)

    def save_model(self, request, obj, form, change):
        if not change:
            instance, plaintext = APIKey.create_key(
                label=obj.label,
                owner=obj.owner,
                allowed_origins=obj.allowed_origins,
            )
            obj.pk = instance.pk
            obj.key_hash = instance.key_hash
            obj.created_at = instance.created_at
            obj._plaintext_key = plaintext
        else:
            obj.save()

    def response_add(self, request, obj, post_url_continue=None):
        """
        After creating a key, redirect to its change page with a short-lived
        signed token in the query string so the modal can render the plaintext.
        """
        if hasattr(obj, "_plaintext_key"):
            from django.http import HttpResponseRedirect

            token = _make_token(obj._plaintext_key)
            change_url = reverse("admin:api_apikey_change", args=[obj.pk])
            return HttpResponseRedirect(
                f"{change_url}?{urlencode({'_key_token': token})}"
            )
        return super().response_add(request, obj, post_url_continue)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}

        token = request.GET.get("_key_token", "")
        if token:
            plaintext = _verify_token(token)
            if plaintext:
                extra_context["new_api_key_plaintext"] = plaintext

        return super().change_view(
            request, object_id, form_url, extra_context=extra_context
        )

    @admin.display(description="API Key")
    def plaintext_notice(self, obj):
        return format_html(
            '<span style="color:#999;font-size:0.9rem;">'
            "The bearer token is stored as a SHA-256 hash and cannot be recovered. "
            "Revoke and create a new key if the plaintext is lost."
            "</span>"
        )


# ---------------------------------------------------------------------------
# APIKeyUsage admin (read-only)
# ---------------------------------------------------------------------------


@admin.register(APIKeyUsage)
class APIKeyUsageAdmin(admin.ModelAdmin):
    list_display = (
        "api_key",
        "endpoint",
        "timestamp",
        "ip_address",
        "user_agent",
        "referer",
    )
    list_filter = ("api_key", "endpoint")
    readonly_fields = ("api_key", "timestamp", "ip_address", "user_agent")
    ordering = ("-timestamp",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
