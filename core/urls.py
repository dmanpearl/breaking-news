from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "core"

urlpatterns = [
    path("", RedirectView.as_view(url="/messages/"), name="home"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/", views.profile_view, name="profile"),
    path("preferences/sidebar-width/", views.save_sidebar_width, name="save_sidebar_width"),
    path("preferences/reset/", views.reset_preferences, name="reset_preferences"),
]
