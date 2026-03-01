from django import forms
from .models import Message


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["headline", "body", "image"]
        widgets = {
            "headline": forms.TextInput(attrs={"placeholder": "Headline..."}),
            "body": forms.Textarea(attrs={"rows": 6, "placeholder": "Message body..."}),
        }

    def clean(self):
        cleaned = super().clean()
        headline = cleaned.get("headline", "").strip()
        body = cleaned.get("body", "").strip()
        image = cleaned.get("image")
        # Keep existing image when editing (image field is empty on unchanged file)
        has_image = bool(image) or bool(
            self.instance and self.instance.pk and self.instance.image
        )
        if not headline and not body and not has_image:
            raise forms.ValidationError(
                "A message must have at least a Headline, Body, or Attachment."
            )
        return cleaned
