"""
core/ui_settings.py

Per-user UI preference persistence via UserPreferences.ui_settings (JSONField).

Namespaces follow feature slugs, e.g. "recent_features".

Public API
----------
get_ui_settings(user, namespace)       -> dict   (empty dict if not set)
set_ui_settings(user, namespace, data) -> None   (shallow-merges data)
"""

from __future__ import annotations

from typing import Any


def _prefs(user):
    """Return the UserPreferences for user, creating it if absent."""
    from .models import UserPreferences

    prefs, _ = UserPreferences.objects.get_or_create(user=user)
    return prefs


def get_ui_settings(user, namespace: str) -> dict:
    """Return the saved settings dict for the given namespace."""
    prefs = _prefs(user)
    blob = prefs.ui_settings or {}
    return dict(blob.get(namespace, {}))


def set_ui_settings(user, namespace: str, data: dict[str, Any]) -> None:
    """Shallow-merge *data* into the user's settings for *namespace*."""
    prefs = _prefs(user)
    blob = dict(prefs.ui_settings or {})
    existing = dict(blob.get(namespace, {}))
    existing.update(data)
    blob[namespace] = existing
    prefs.ui_settings = blob
    prefs.save(update_fields=["ui_settings"])


def reset_ui_settings(user, namespace: str | None = None) -> None:
    """
    Clear saved settings.
    - namespace=None  -> clears all namespaces (full reset)
    - namespace=<str> -> clears only that namespace
    """
    prefs = _prefs(user)
    if namespace is None:
        prefs.ui_settings = {}
    else:
        blob = dict(prefs.ui_settings or {})
        blob.pop(namespace, None)
        prefs.ui_settings = blob
    prefs.save(update_fields=["ui_settings"])
