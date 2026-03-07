from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

from api.api import api as ninja_api
from api.redoc import redoc_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", ninja_api.urls),
    # Redoc — separate docs renderer at /api/v1/redoc
    path("api/v1/redoc", redoc_view, name="api-redoc"),
    path("api/v1/redoc/", RedirectView.as_view(url="/api/v1/redoc", permanent=True)),
    # Trailing-slash redirect for Swagger docs
    path("api/v1/docs/", RedirectView.as_view(url="/api/v1/docs", permanent=True)),
    path("", include("core.urls", namespace="core")),
    path("messages/", include("messaging.urls", namespace="messaging")),
    path("connections/", include("connections.urls", namespace="connections")),
    path("api-admin/", include("api.urls", namespace="api_app")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
