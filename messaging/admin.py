from django.contrib import admin
from .models import DeliveryReceipt, Message


class DeliveryReceiptInline(admin.TabularInline):
    model = DeliveryReceipt
    extra = 0
    readonly_fields = ("connection", "success", "remote_message_id", "error", "sent_at")
    can_delete = False


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("headline", "sent", "created_by", "created_at")
    list_filter = ("sent",)
    readonly_fields = ("sent", "created_at", "updated_at")
    inlines = [DeliveryReceiptInline]
