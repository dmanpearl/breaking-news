from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import LoginForm, RegisterForm

_SIDEBAR_MIN = 180
_SIDEBAR_MAX = 750
_SIDEBAR_DEFAULT = 280


def login_view(request):
    if request.user.is_authenticated:
        return redirect("messaging:index")
    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect(request.GET.get("next", "messaging:index"))
    return render(request, "core/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("core:login")


@login_required
def profile_view(request):
    from messaging.models import Message
    from connections.models import Connection

    return render(
        request,
        "core/profile.html",
        {
            "history": Message.objects.all(),
            "connections": Connection.objects.all(),
        },
    )


@login_required
@require_POST
def save_sidebar_width(request):
    """Save the user's preferred sidebar width. Called by the drag handler."""
    from .models import UserPreferences

    try:
        width = int(request.POST.get("width", _SIDEBAR_DEFAULT))
    except (TypeError, ValueError):
        return JsonResponse({"error": "invalid width"}, status=400)

    width = max(_SIDEBAR_MIN, min(_SIDEBAR_MAX, width))

    prefs = UserPreferences.for_user(request.user)
    prefs.sidebar_width = width
    prefs.save(update_fields=["sidebar_width"])
    return JsonResponse({"width": width})


@login_required
@require_POST
def save_history_expand_all(request):
    """Save the user's expand-all preference for the history panel."""
    from .models import UserPreferences

    value = request.POST.get("value", "false").lower() == "true"
    prefs = UserPreferences.for_user(request.user)
    prefs.history_expand_all = value
    prefs.save(update_fields=["history_expand_all"])
    return JsonResponse({"value": value})


@login_required
@require_POST
def reset_preferences(request):
    """Reset all user preferences to defaults."""
    from .models import UserPreferences

    prefs = UserPreferences.for_user(request.user)
    from .ui_settings import reset_ui_settings

    prefs.sidebar_width = _SIDEBAR_DEFAULT
    prefs.history_expand_all = False
    prefs.save(update_fields=["sidebar_width", "history_expand_all"])
    reset_ui_settings(request.user)
    return redirect(request.POST.get("next", "messaging:index"))


@login_required
def recent_features(request):
    """Display the full paginated list of recent features."""
    import json as _json
    from django.core.paginator import Paginator
    from .recent_features import get_features

    features_list = get_features()
    paginator = Paginator(features_list, 20)
    features_page = paginator.get_page(request.GET.get("page", 1))
    return render(request, "core/recent_features.html", {"features_page": features_page})


@login_required
def feature_detail(request, feature_id):
    """Display full detail for a single recent feature."""
    from .recent_features import get_features

    features = get_features()
    feature = next((f for f in features if f["id"] == feature_id), None)
    if feature is None:
        from django.http import Http404
        raise Http404("Feature not found")
    idx = features.index(feature)
    prev_feature = features[idx - 1] if idx > 0 else None
    next_feature = features[idx + 1] if idx < len(features) - 1 else None
    return render(request, "core/feature_detail.html", {
        "feature": feature,
        "prev_feature": prev_feature,
        "next_feature": next_feature,
    })


@login_required
@require_POST
def api_dismiss_recent_feature(request):
    """POST — save dismissal of a feature banner by ID."""
    import json as _json
    from .ui_settings import set_ui_settings

    try:
        data = _json.loads(request.body)
    except (_json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    feature_id = data.get("id", "")
    if not feature_id:
        return JsonResponse({"error": "id required"}, status=400)
    set_ui_settings(request.user, "recent_features", {"dismissed_id": feature_id})
    return JsonResponse({"ok": True})
