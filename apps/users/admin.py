"""Регистрация моделей пользователей в административной панели."""

from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group

from apps.users.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Административный интерфейс для управления пользователями системы."""

    list_display = ("email", "first_name", "last_name", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)
    readonly_fields = ("date_joined", "last_login")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Персональные данные", {"fields": ("first_name", "last_name", "role")}),
        ("Права доступа", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Важные даты", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "first_name", "last_name", "role", "password1", "password2"),
            },
        ),
    )


admin.site.unregister(Group)
