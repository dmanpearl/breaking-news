from .models import SiteSettings, UserPreferences

_SIDEBAR_DEFAULT = 280


def site_settings(request):
    settings = SiteSettings.get()
    timeout_ms = settings.inactivity_timeout_mins * 60 * 1000
    warning_ms = settings.inactivity_warning_secs * 1000
    warn_after_ms = timeout_ms - warning_ms

    sidebar_width = _SIDEBAR_DEFAULT
    history_expand_all = False
    if request.user.is_authenticated:
        try:
            prefs = request.user.preferences
            sidebar_width = prefs.sidebar_width
            history_expand_all = prefs.history_expand_all
        except UserPreferences.DoesNotExist:
            pass

    return {
        "site_settings": settings,
        "inactivity_timeout_ms": timeout_ms,
        "inactivity_warn_after_ms": warn_after_ms,
        "inactivity_warning_ms": warning_ms,
        "sidebar_width": sidebar_width,
        "history_expand_all": history_expand_all,
    }
