from django.contrib import admin
from django.utils.html import format_html

from .models import APIKey

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
    fields = ("label", "owner", "is_active", "plaintext_notice", "key_hash", "created_at", "last_used_at")
    search_fields = ("label", "owner__username", "owner__email")

    def get_fields(self, request, obj=None):
        # On the add form, hide the hash fields — they don't exist yet.
        if obj is None:
            return ("label", "owner")
        return super().get_fields(request, obj)

    def save_model(self, request, obj, form, change):
        if not change:
            # New key — generate plaintext and hash, store the plaintext
            # temporarily on the instance so we can display it once.
            instance, plaintext = APIKey.create_key(
                label=obj.label,
                owner=obj.owner,
            )
            # Transfer to the form object so Django admin shows the saved record.
            obj.pk = instance.pk
            obj.key_hash = instance.key_hash
            obj.created_at = instance.created_at
            obj._plaintext_key = plaintext
        else:
            obj.save()

    def response_add(self, request, obj, post_url_continue=None):
        # Stash the plaintext in the session so the change view can show it.
        if hasattr(obj, "_plaintext_key"):
            request.session["_new_api_key"] = obj._plaintext_key
        return super().response_add(request, obj, post_url_continue)

    @admin.display(description="API Key (shown once)")
    def plaintext_notice(self, obj):
        # Pull the key from the session if this is a freshly created key.
        from django.contrib.admin import site

        request = getattr(self, "_current_request", None)
        if request and "_new_api_key" in request.session:
            key = request.session.pop("_new_api_key")
            return format_html(
                '<div style="background:#fffbcc;border:1px solid #e6c800;'
                'padding:10px;border-radius:4px;font-family:monospace;font-size:1rem;">'
                "<strong>⚠ Copy this key now — it will never be shown again:</strong><br><br>"
                '<span id="bn-api-key" style="user-select:all;font-size:1.1rem;font-family:monospace;">{}</span>'
                '&nbsp;&nbsp;<button type="button" title="Copy to clipboard" '
                'onclick="(function(){{var t=document.getElementById(\'bn-api-key\').innerText;'
                'navigator.clipboard.writeText(t).then(function(){{var b=document.getElementById(\'bn-copy-btn\');'
                'b.innerHTML=\'&#10003; Copied\';setTimeout(function(){{b.innerHTML=\'&#128203; Copy\'}},2000);}})}})()" '
                'id="bn-copy-btn" style="cursor:pointer;padding:4px 10px;border:1px solid #ccc;'
                'border-radius:4px;background:#fff;font-size:0.9rem;vertical-align:middle;">&#128203; Copy</button>'
                "</div>",
                key,
            )
        return format_html(
            '<span style="color:#999;">Key is stored as a hash and cannot be recovered. '
            "Revoke and create a new key if lost.</span>"
        )

    def change_view(self, request, object_id, form_url="", extra_context=None):
        # Make the request accessible to plaintext_notice().
        self._current_request = request
        return super().change_view(request, object_id, form_url, extra_context)
