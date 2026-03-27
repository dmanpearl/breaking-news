from django.conf import settings
from django.db import models

from connections.models import Connection


class Message(models.Model):
    headline = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    image = models.FileField(
        upload_to="message_images/",
        blank=True,
        null=True,
        help_text="Accepted: images (PNG, JPG, GIF, WEBP) and PDF files.",
    )
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
    def display_title(self) -> str:
        """
        Title for the history sidebar.
        Falls back to a description built from the attachment when there is
        no headline and no body.
        """
        if self.headline:
            return self.headline
        if self.body:
            # First non-empty line -- full text, truncated visually in the sidebar via CSS.
            return self.body.strip().splitlines()[0]
        if self.image:
            try:
                import os

                size = self.image.size  # bytes
                name = self.image.name or ""
                ext = os.path.splitext(name)[1].upper().lstrip(".") or "FILE"
                if size < 1024:
                    size_str = f"{size} B"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size / (1024 * 1024):.1f} MB"
                title = f"{ext} Attachment ({size_str})"
                # For PDFs include the filename so the collapsed and expanded
                # states are identical (no expand triangle needed).
                if name.lower().endswith(".pdf"):
                    bare = os.path.basename(name)
                    # Strip the upload timestamp prefix (16 chars) that
                    # Cloudinary/Django storage prepends.
                    display_name = bare[16:] if len(bare) > 16 else bare
                    if display_name:
                        title = f"{title} \u00b7 {display_name}"
                return title
            except Exception:
                return "Attachment"
        return "(empty)"

    @property
    def display_pdf_label(self) -> str:
        """Filename + human-readable filesize for the PDF download link.
        Example: 'report.pdf (21.6 KB)'
        """
        try:
            import os

            name = self.image.name or ""
            bare = os.path.basename(name)
            # Strip the upload timestamp prefix (16 chars).
            display_name = bare[16:] if len(bare) > 16 else bare
            size = self.image.size
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024 * 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size / (1024 * 1024):.1f} MB"
            return f"{display_name} ({size_str})" if display_name else f"attachment.pdf ({size_str})"
        except Exception:
            return "attachment.pdf"

    @property
    def display_sender_full(self) -> str:
        """Full name if available, otherwise username. For the detail view."""
        u = self.created_by
        if not u:
            return "Unknown"
        full = f"{u.first_name} {u.last_name}".strip()
        return full if full else u.username

    @property
    def display_sender_short(self) -> str:
        """'First L.' if available, 'First' if no last name, else username. For history list."""
        u = self.created_by
        if not u:
            return ""
        if u.first_name and u.last_name:
            return f"{u.first_name} {u.last_name[0]}"
        if u.first_name:
            return u.first_name
        return u.username

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
        from django.db.models import Count, Q
        agg = self.receipts.aggregate(
            total=Count("id"),
            success=Count("id", filter=Q(success=True)),
        )
        total = agg["total"]
        success = agg["success"]
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
