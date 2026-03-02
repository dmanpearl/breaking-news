import os
from django import forms
from .models import Message

ALLOWED_MIMES = {
    "image/png", "image/jpeg", "image/gif", "image/webp", "application/pdf",
}
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf"}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8 MB — Discord webhook hard limit


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["headline", "body", "image"]
        widgets = {
            "headline": forms.Textarea(
                attrs={
                    "rows": 1,
                    "placeholder": "Headline...",
                    "style": "resize:none;overflow:hidden;",
                }
            ),
            "body": forms.Textarea(attrs={"rows": 6, "placeholder": "Message body..."}),
            "image": forms.ClearableFileInput(attrs={
                "accept": "image/png,image/jpeg,image/gif,image/webp,application/pdf,.pdf",
            }),
        }

    def __init__(self, *args, headline_enabled=True, **kwargs):
        super().__init__(*args, **kwargs)
        if not headline_enabled:
            self.fields.pop("headline", None)
        self.fields["image"].label = "Attachment"

    def clean_image(self):
        f = self.cleaned_data.get("image")
        if not f or not hasattr(f, "name"):
            return f  # unchanged existing file or empty
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise forms.ValidationError(
                f"Unsupported file type '{ext}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )
        # Size check — guard against files that would be rejected by Discord
        size = getattr(f, "size", None)
        if size and size > MAX_UPLOAD_BYTES:
            mb = size / (1024 * 1024)
            raise forms.ValidationError(
                f"File is {mb:.1f} MB. Discord rejects attachments over 8 MB."
            )
        return f

    def clean(self):
        cleaned = super().clean()
        headline = cleaned.get("headline", "").replace("\n", " ").strip()
        body = cleaned.get("body", "").strip()
        image = cleaned.get("image")
        # Keep existing attachment when editing (field is empty on unchanged file)
        has_image = bool(image) or bool(
            self.instance and self.instance.pk and self.instance.image
        )
        if not headline and not body and not has_image:
            raise forms.ValidationError(
                "A message must have at least a Headline, Body, or Attachment."
            )
        return cleaned
