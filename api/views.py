from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.utils.dateparse import parse_date

from .models import APIKey, APIKeyUsage

PAGE_SIZE = 50


def _is_staff(user):
    return user.is_active and (user.is_staff or user.is_superuser)


@login_required
def usage_log(request):
    if not _is_staff(request.user):
        return HttpResponseForbidden("Staff access required.")

    qs = APIKeyUsage.objects.select_related("api_key").order_by("-timestamp")

    # --- Filters ---
    all_keys = APIKey.objects.order_by("label")

    key_id = request.GET.get("key_id", "")
    date_str = request.GET.get("date", "")
    ua_filter = request.GET.get("user_agent", "").strip()

    if key_id:
        qs = qs.filter(api_key_id=key_id)

    if date_str:
        parsed_date = parse_date(date_str)
        if parsed_date:
            qs = qs.filter(timestamp__date=parsed_date)

    if ua_filter:
        qs = qs.filter(user_agent__icontains=ua_filter)

    # --- Pagination ---
    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "api/usage.html",
        {
            "page_obj": page_obj,
            "all_keys": all_keys,
            "selected_key_id": key_id,
            "selected_date": date_str,
            "ua_filter": ua_filter,
            "total_count": qs.count(),
        },
    )
