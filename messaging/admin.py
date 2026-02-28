from django.contrib import admin, messages
from django.utils.html import format_html

from .models import DeliveryReceipt, Message


class DeliveryReceiptInline(admin.TabularInline):
    model = DeliveryReceipt
    extra = 0
    readonly_fields = (
        "connection",
        "success",
        "remote_message_id",
        "error",
        "sent_at",
    )
    can_delete = False


def mark_unsent(modeladmin, request, queryset):
    updated = queryset.update(sent=False, last_error="")
    messages.success(request, f"{updated} message(s) marked as unsent.")


mark_unsent.short_description = "Mark selected messages as unsent (draft)"


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "headline",
        "sent",
        "send_status_display",
        "created_by",
        "created_at",
    )
    list_filter = ("sent",)
    readonly_fields = ("sent", "created_at", "updated_at", "error_detail")
    actions = [mark_unsent]
    inlines = [DeliveryReceiptInline]

    fieldsets = (
        (
            "Message",
            {"fields": ("headline", "body", "image", "created_by")},
        ),
        (
            "Status",
            {
                "fields": ("sent", "error_detail", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Error")
    def send_status_display(self, obj):
        if obj.sent:
            return format_html('<span style="color:#155724;">✓ Sent</span>')
        if obj.last_error:
            return format_html(
                '<span style="color:#721c24;" title="{}">✗ Failed</span>',
                obj.last_error[:200],
            )
        return format_html('<span style="color:#856404;">— Draft</span>')

    @admin.display(description="Last Send Error")
    def error_detail(self, obj):
        if not obj.last_error:
            return "—"
        return format_html(
            '<pre style="white-space:pre-wrap;font-size:0.85rem;max-width:700px;">{}</pre>',
            obj.last_error,
        )
