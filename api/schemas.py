from datetime import datetime
from typing import Optional

from ninja import Schema


class MessageSchema(Schema):
    id: int
    headline: str
    body: str
    image_url: Optional[str] = None
    sent: bool
    created_at: datetime
    updated_at: datetime
    sender: Optional[str] = None

    @staticmethod
    def resolve_image_url(obj):
        """Return the absolute URL of the image/attachment if one exists."""
        if not obj.image:
            return None
        try:
            return obj.image.url
        except Exception:
            return None

    @staticmethod
    def resolve_sender(obj):
        return obj.display_sender_full if obj.created_by else None


class MessageListSchema(Schema):
    count: int
    results: list[MessageSchema]


class ErrorSchema(Schema):
    detail: str


class HealthSchema(Schema):
    status: str
    version: str = "1.0"
