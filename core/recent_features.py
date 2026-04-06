"""
core/recent_features.py

Loads and caches recent_features.yaml from the project root.

Public API
----------
get_features()   -> list of dicts, newest-first
get_latest()     -> first dict in the list, or None
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

_YAML_PATH = Path(__file__).resolve().parent.parent / "recent_features.yaml"


@lru_cache(maxsize=1)
def get_features() -> list[dict]:
    """
    Return all recent features, newest-first.
    Cached after first load — server restart picks up YAML changes.
    """
    try:
        with open(_YAML_PATH, "r") as f:
            data = yaml.safe_load(f)
        return data.get("recent_features", [])
    except (FileNotFoundError, yaml.YAMLError):
        return []


def get_latest() -> dict | None:
    """Return the most recent feature entry, or None if the list is empty."""
    features = get_features()
    return features[0] if features else None
