from django.urls import path
from . import views

app_name = "connections"

urlpatterns = [
    path("status/", views.status_view, name="status"),
]
