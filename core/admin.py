from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import SiteSettings, User


class UserCreationFormOptionalEmail(UserCreationForm):
    """UserCreationForm with email made optional."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = False

    def clean_email(self):
        """Convert empty string to None so the unique constraint allows multiple blank emails."""
        return self.cleaned_data.get("email") or None


class UserChangeFormOptionalEmail(UserChangeForm):
    """UserChangeForm with email made optional."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = False

    def clean_email(self):
        """Convert empty string to None so the unique constraint allows multiple blank emails."""
        return self.cleaned_data.get("email") or None


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserChangeFormOptionalEmail
    add_form = UserCreationFormOptionalEmail
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "user_groups",
        "staff_check",
        "superuser_check",
    )
    list_display_links = ("username",)
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Extended Info", {"fields": ("phone", "bio")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            "Extended Info",
            {"fields": ("email", "first_name", "last_name", "phone", "bio")},
        ),
    )

    @admin.display(description="Groups")
    def user_groups(self, obj):
        names = ", ".join(g.name for g in obj.groups.all())
        return names or "—"

    @admin.display(description="Staff", boolean=False)
    def staff_check(self, obj):
        # Show green checkmark for True, blank for False (no red X)
        if obj.is_staff:
            return "✔"
        return ""

    @admin.display(description="Admin", boolean=False)
    def superuser_check(self, obj):
        if obj.is_superuser:
            return "✔"
        return ""


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
