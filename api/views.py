from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.utils.dateparse import parse_date

from .models import APIKey, APIKeyUsage

PAGE_SIZE = 50

# Choices for the endpoint filter dropdown.
# Value is the raw path prefix stored in the DB; label is the friendly name.
ENDPOINT_CHOICES = [
    ("/api/v1/stream", "Stream"),
    ("/api/v1/messages/latest", "Latest Message"),
    ("/api/v1/messages", "Messages"),
    ("/api/v1/health", "Health"),
    ("/api/v1/docs", "Docs"),
    ("/api/v1/redoc", "Redoc"),
]


def _is_staff(user):
    return user.is_active and (user.is_staff or user.is_superuser)


@login_required
def usage_log(request):
    if not _is_staff(request.user):
        return HttpResponseForbidden("Staff access required.")

    qs = APIKeyUsage.objects.select_related("api_key").order_by("-timestamp")

    # --- Filters ---
    all_keys = APIKey.objects.order_by("label")

    # key_id must be a valid integer PK to avoid cross-key leakage.
    raw_key_id = request.GET.get("key_id", "").strip()
    key_id = ""
    if raw_key_id:
        try:
            key_id = str(int(raw_key_id))  # validates it is an integer
            qs = qs.filter(api_key_id=int(key_id))
        except (ValueError, TypeError):
            key_id = ""

    date_str = request.GET.get("date", "").strip()
    if date_str:
        parsed_date = parse_date(date_str)
        if parsed_date:
            qs = qs.filter(timestamp__date=parsed_date)

    ua_filter = request.GET.get("user_agent", "").strip()
    if ua_filter:
        qs = qs.filter(user_agent__icontains=ua_filter)

    # Endpoint filter: startswith covers /api/v1/messages AND /api/v1/messages/{id}.
    endpoint_filter = request.GET.get("endpoint", "").strip()
    if endpoint_filter:
        qs = qs.filter(endpoint__startswith=endpoint_filter)

    total_count = qs.count()

    # --- Pagination ---
    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # Build a stable query string for pagination links that preserves filters.
    filter_params = {}
    if key_id:
        filter_params["key_id"] = key_id
    if date_str:
        filter_params["date"] = date_str
    if ua_filter:
        filter_params["user_agent"] = ua_filter
    if endpoint_filter:
        filter_params["endpoint"] = endpoint_filter
    filter_qs = urlencode(filter_params)

    return render(
        request,
        "api/usage.html",
        {
            "page_obj": page_obj,
            "all_keys": all_keys,
            "selected_key_id": key_id,
            "selected_date": date_str,
            "ua_filter": ua_filter,
            "endpoint_filter": endpoint_filter,
            "endpoint_choices": ENDPOINT_CHOICES,
            "total_count": total_count,
            "filter_qs": filter_qs,
        },
    )
