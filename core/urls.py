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
    path("preferences/history-expand-all/", views.save_history_expand_all, name="save_history_expand_all"),
    path("preferences/reset/", views.reset_preferences, name="reset_preferences"),
    path("features/", views.recent_features, name="recent_features"),
    path("features/<str:feature_id>/", views.feature_detail, name="feature_detail"),
    path("api/features/dismiss/", views.api_dismiss_recent_feature, name="api_dismiss_recent_feature"),
]
