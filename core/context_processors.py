from .models import SiteSettings, UserPreferences

_SIDEBAR_DEFAULT = 280


def site_settings(request):
    settings = SiteSettings.get()
    timeout_ms = settings.inactivity_timeout_mins * 60 * 1000
    warning_ms = settings.inactivity_warning_secs * 1000
    warn_after_ms = timeout_ms - warning_ms

    sidebar_width = _SIDEBAR_DEFAULT
    if request.user.is_authenticated:
        try:
            sidebar_width = request.user.preferences.sidebar_width
        except UserPreferences.DoesNotExist:
            pass

    return {
        "site_settings": settings,
        "inactivity_timeout_ms": timeout_ms,
        "inactivity_warn_after_ms": warn_after_ms,
        "inactivity_warning_ms": warning_ms,
        "sidebar_width": sidebar_width,
    }
