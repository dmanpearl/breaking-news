from django.urls import path
from . import views

app_name = "messaging"

urlpatterns = [
    path("", views.index, name="index"),
    path("new/", views.message_create, name="create"),
    path("<int:pk>/", views.message_detail, name="detail"),
    path("<int:pk>/edit/", views.message_edit, name="edit"),
    path("<int:pk>/send/", views.message_send, name="send"),
    path("<int:pk>/delete/", views.message_delete, name="delete"),
    path("<int:pk>/delete/confirm/", views.message_delete_confirm, name="delete_confirm"),
    path("history/", views.history_partial, name="history"),
    path("landing/", views.landing, name="landing"),
]
