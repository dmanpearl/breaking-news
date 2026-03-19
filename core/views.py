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
    prefs.sidebar_width = _SIDEBAR_DEFAULT
    prefs.history_expand_all = False
    prefs.save(update_fields=["sidebar_width", "history_expand_all"])
    return redirect(request.POST.get("next", "messaging:index"))
