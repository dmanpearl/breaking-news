import time as _status_time

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Connection

_status_cache: dict = {"data": None, "expires": 0.0}
_STATUS_TTL = 300  # seconds — connections change rarely; mothballed connections never


@login_required
def status_view(request):
    now = _status_time.monotonic()
    if _status_cache["data"] is None or now >= _status_cache["expires"]:
        _status_cache["data"] = list(
            Connection.objects.values(
                "id", "name", "connection_type", "enabled", "status", "status_message"
            )
        )
        _status_cache["expires"] = now + _STATUS_TTL
    return JsonResponse({"connections": _status_cache["data"]})
