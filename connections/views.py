from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Connection


@login_required
def status_view(request):
    data = list(
        Connection.objects.values(
            "id", "name", "connection_type", "enabled", "status", "status_message"
        )
    )
    return JsonResponse({"connections": data})
