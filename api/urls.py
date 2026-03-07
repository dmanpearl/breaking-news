from django.urls import path

from . import views

app_name = "api_app"

urlpatterns = [
    path("usage/", views.usage_log, name="usage"),
]
