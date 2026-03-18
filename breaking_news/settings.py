"""
Breaking News - Django settings
Supports SQLite (dev) and PostgreSQL (Railway).
"""

import os
from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("SECRET_KEY", default="dev-secret-key-change-in-production")
DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="*", cast=Csv())

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "phonenumber_field",
    "cloudinary_storage",
    "cloudinary",
    "ninja",
    "corsheaders",
    "core",
    "messaging",
    "connections",
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "breaking_news.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site_settings",
                "messaging.context_processors.connections",
            ],
        },
    },
]

WSGI_APPLICATION = "breaking_news.wsgi.application"

import dj_database_url  # type: ignore

# DATABASE_PUBLIC_URL is the externally reachable URL (used by railway run locally).
# DATABASE_URL is the private internal URL (used by the deployed app inside Railway).
# Prefer PUBLIC when available so local railway run commands can connect.
DATABASE_URL = config("DATABASE_PUBLIC_URL", default="") or config(
    "DATABASE_URL", default=""
)

if DATABASE_URL:
    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=60)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "core.User"
LOGIN_URL = "core:login"
LOGIN_REDIRECT_URL = "messaging:index"
LOGOUT_REDIRECT_URL = "core:login"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Cloudinary — used in production (Railway) when CLOUDINARY_URL env var is set.
# Falls back to local disk storage in development (runserver).
CLOUDINARY_URL = config("CLOUDINARY_URL", default="")
if CLOUDINARY_URL:
    DEFAULT_FILE_STORAGE = "breaking_news.storage.SmartMediaCloudinaryStorage"
    CLOUDINARY_STORAGE = {
        "CLOUDINARY_URL": CLOUDINARY_URL,
        # "raw" allows Cloudinary to store non-image files (e.g. PDFs) without
        # attempting image processing on them. Without this, PDF uploads are
        # rejected by Cloudinary with an "Invalid image file" error.
        "MEDIA_TAG": "media",
        "INVALID_VIDEO_ERROR_MESSAGE": "Please upload a valid file.",
        "EXCLUDE_DELETE_ORPHANED_MEDIA_PATHS": (),
        "STATIC_TAG": "static",
        "STATICFILES_MANIFEST_ROOT": BASE_DIR / "manifest",
        "MAGIC_FILE_PATH": "magic",
        "PREFIX": "",
        "ALLOWED_RESOURCE_TYPES": ["image", "raw"],
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

PHONENUMBER_DEFAULT_REGION = "US"

# HTTPS / CSRF settings for production
# CSRF_TRUSTED_ORIGINS is loaded from the env var. When not set we fall back to
# an empty list, which causes Django to reject any POST (including login) from a
# custom domain. The if-not-DEBUG block below ensures the production domains are
# always trusted even if the env var is missing or misconfigured.
_csrf_env = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())
CSRF_TRUSTED_ORIGINS = _csrf_env if _csrf_env else []

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Railway terminates SSL at the load balancer and forwards requests to Django
    # over plain HTTP internally. This header tells Django to trust Railway's
    # X-Forwarded-Proto header so it knows the original request was HTTPS.
    # Without this, CSRF checks can fail and secure cookie flags behave incorrectly.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # Redirect any plain HTTP requests to HTTPS.
    SECURE_SSL_REDIRECT = True
    # Ensure production domains are always in CSRF_TRUSTED_ORIGINS regardless of
    # whether the env var was set. Merges with any env-var entries without duplicating.
    _production_origins = [
        "https://breakingnewsguys.com",
        "https://www.breakingnewsguys.com",
    ]
    CSRF_TRUSTED_ORIGINS = list(
        dict.fromkeys(CSRF_TRUSTED_ORIGINS + _production_origins)
    )

# ── Logging ──────────────────────────────────────────────────────────────────
# Prints WARNING+ from Django internals and DEBUG+ from our own apps to the
# runserver console. Without this, logger.error() in app code goes nowhere.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "connections": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "messaging": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

# ── CORS ──────────────────────────────────────────────────────────────────────
# Allow the Breaking News reader app to call the API from the browser.
# Add any additional reader origins to CORS_ALLOWED_ORIGINS via the env var
# CORS_ALLOWED_ORIGINS (comma-separated), or extend the list below.
_cors_env = config("CORS_ALLOWED_ORIGINS", default="", cast=Csv())
CORS_ALLOWED_ORIGINS = list(_cors_env) if _cors_env else []

_reader_origins = [
    "https://reader.breakingnewsguys.com",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]
CORS_ALLOWED_ORIGINS = list(dict.fromkeys(CORS_ALLOWED_ORIGINS + _reader_origins))

# Allow any *.up.railway.app subdomain so Railway preview/staging URLs work
# without needing to hardcode each one. Production traffic uses the explicit
# reader.breakingnewsguys.com entry above.
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://[\w-]+\.up\.railway\.app$",
]

# Only expose the API paths — the Django UI does not need CORS.
CORS_URLS_REGEX = r"^/api/v1/.*$"

# Allow the Authorization header and standard methods.
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
]
