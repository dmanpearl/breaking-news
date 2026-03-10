from urllib.parse import urlencode

from django.contrib.auth import get_user_model
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

    qs = APIKeyUsage.objects.select_related("api_key", "api_key__owner").order_by("-timestamp")

    # --- Filter data ---
    all_keys = APIKey.objects.select_related("owner").order_by("label")
    # Distinct accounts that have at least one key, for the account filter dropdown.
    User = get_user_model()
    all_owners = User.objects.filter(api_keys__isnull=False).distinct().order_by("username")

    # --- Key filter ---
    raw_key_id = request.GET.get("key_id", "").strip()
    key_id = ""
    if raw_key_id:
        try:
            key_id = str(int(raw_key_id))
            qs = qs.filter(api_key_id=int(key_id))
        except (ValueError, TypeError):
            key_id = ""

    # --- Owner filter (filters by the key's associated owner user) ---
    raw_owner_id = request.GET.get("owner_id", "").strip()
    owner_id = ""
    if raw_owner_id:
        try:
            owner_id = str(int(raw_owner_id))
            qs = qs.filter(api_key__owner_id=int(owner_id))
        except (ValueError, TypeError):
            owner_id = ""

    # --- Date filter ---
    date_str = request.GET.get("date", "").strip()
    if date_str:
        parsed_date = parse_date(date_str)
        if parsed_date:
            qs = qs.filter(timestamp__date=parsed_date)

    # --- User agent filter ---
    ua_filter = request.GET.get("user_agent", "").strip()
    if ua_filter:
        qs = qs.filter(user_agent__icontains=ua_filter)

    # --- Endpoint filter ---
    endpoint_filter = request.GET.get("endpoint", "").strip()
    if endpoint_filter:
        qs = qs.filter(endpoint__startswith=endpoint_filter)

    total_count = qs.count()

    # --- Pagination ---
    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # Build a stable query string for pagination links that preserves all filters.
    filter_params = {}
    if key_id:
        filter_params["key_id"] = key_id
    if owner_id:
        filter_params["owner_id"] = owner_id
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
            "all_owners": all_owners,
            "selected_key_id": key_id,
            "selected_owner_id": owner_id,
            "selected_date": date_str,
            "ua_filter": ua_filter,
            "endpoint_filter": endpoint_filter,
            "endpoint_choices": ENDPOINT_CHOICES,
            "total_count": total_count,
            "filter_qs": filter_qs,
        },
    )
