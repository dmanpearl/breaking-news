from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import SiteSettings, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
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
