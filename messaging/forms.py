from django import forms
from .models import Message


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["headline", "body", "image"]
        widgets = {
            "headline": forms.TextInput(attrs={"placeholder": "Headline…"}),
            "body": forms.Textarea(attrs={"rows": 6, "placeholder": "Message body…"}),
        }
