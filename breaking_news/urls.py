from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls", namespace="core")),
    path("messages/", include("messaging.urls", namespace="messaging")),
    path("connections/", include("connections.urls", namespace="connections")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
