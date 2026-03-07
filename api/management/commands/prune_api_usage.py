from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from api.models import APIKeyUsage

RETENTION_DAYS = 120


class Command(BaseCommand):
    help = f"Delete APIKeyUsage rows older than {RETENTION_DAYS} days."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=RETENTION_DAYS)
        deleted, _ = APIKeyUsage.objects.filter(timestamp__lt=cutoff).delete()
        self.stdout.write(f"Pruned {deleted} API usage log rows older than {RETENTION_DAYS} days.")
