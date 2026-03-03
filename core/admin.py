from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import SiteSettings, User


class UserCreationFormOptionalEmail(UserCreationForm):
    """UserCreationForm with email made optional (Django requires it by default)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = False


class UserChangeFormOptionalEmail(UserChangeForm):
    """UserChangeForm with email made optional."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = False


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserChangeFormOptionalEmail
    add_form = UserCreationFormOptionalEmail
    list_display = ("username", "email", "first_name", "last_name", "is_staff")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Extended Info", {"fields": ("phone", "bio")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            "Extended Info",
            {"fields": ("email", "first_name", "last_name", "phone", "bio")},
        ),
    )


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
