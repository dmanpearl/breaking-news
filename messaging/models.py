from django.db import models
from django.conf import settings
from connections.models import Connection


class Message(models.Model):
    headline = models.CharField(max_length=255)
    body = models.TextField()
    image = models.ImageField(upload_to="message_images/", blank=True, null=True)
    sent = models.BooleanField(default=False)
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
