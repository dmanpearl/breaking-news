from django.conf import settings
from django.db import models

from connections.models import Connection


class Message(models.Model):
    headline = models.CharField(max_length=255)
    body = models.TextField()
    image = models.ImageField(upload_to="message_images/", blank=True, null=True)
    sent = models.BooleanField(default=False)
    last_error = models.TextField(
        blank=True,
        help_text="Error detail from the most recent failed send attempt.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="messages",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.headline

    @property
    def can_edit(self) -> bool:
        """
        A message is editable when:
          - It has never been successfully sent (still a draft), OR
          - At least one of its successful delivery connections has
            can_edit_sent = True.

        Unsent / failed messages are always editable because editing them
        just updates the local record — nothing needs to change on Discord.
        """
        if not self.sent:
            return True
        return self.receipts.filter(
            success=True,
            connection__connectiondiscord__can_edit_sent=True,
        ).exists()

    @property
    def delivery_summary(self):
        receipts = self.receipts.all()
        total = receipts.count()
        success = receipts.filter(success=True).count()
        return {"total": total, "success": success, "failed": total - success}


class DeliveryReceipt(models.Model):
    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="receipts"
    )
    connection = models.ForeignKey(
        Connection, on_delete=models.SET_NULL, null=True, related_name="receipts"
    )
    success = models.BooleanField(default=False)
    remote_message_id = models.CharField(max_length=128, blank=True)
    error = models.TextField(blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sent_at"]
        unique_together = [("message", "connection")]

    def __str__(self):
        status = "✓" if self.success else "✗"
        return f"{status} {self.message.headline} → {self.connection}"
