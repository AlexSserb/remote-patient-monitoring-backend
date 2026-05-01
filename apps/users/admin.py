"""Регистрация моделей пользователей в административной панели."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group

from apps.users.models import CaregiverPatient, DoctorPatient, Role, User

if TYPE_CHECKING:
    from django.contrib.admin.options import InlineModelAdmin
    from django.db.models import QuerySet
    from django.http import HttpRequest


class DoctorPatientsInline(admin.TabularInline):
    """Список пациентов, прикреплённых к доктору."""

    model = DoctorPatient
    fk_name = "doctor"
    extra = 0
    raw_id_fields = ("patient",)
    readonly_fields = ("assigned_at",)
    verbose_name = "Пациент"
    verbose_name_plural = "Пациенты"


class PatientDoctorsInline(admin.TabularInline):
    """Список докторов, наблюдающих пациента."""

    model = DoctorPatient
    fk_name = "patient"
    extra = 0
    raw_id_fields = ("doctor",)
    readonly_fields = ("assigned_at",)
    verbose_name = "Доктор"
    verbose_name_plural = "Доктора"


class PatientCaregiversInline(admin.TabularInline):
    """Список опекунов, прикреплённых к пациенту."""

    model = CaregiverPatient
    fk_name = "patient"
    extra = 0
    raw_id_fields = ("caregiver",)
    readonly_fields = ("assigned_at",)
    verbose_name = "Опекун"
    verbose_name_plural = "Опекуны"


class CaregiverPatientsInline(admin.TabularInline):
    """Список пациентов, за которыми наблюдает опекун."""

    model = CaregiverPatient
    fk_name = "caregiver"
    extra = 0
    raw_id_fields = ("patient",)
    readonly_fields = ("assigned_at",)
    verbose_name = "Пациент"
    verbose_name_plural = "Пациенты"


@admin.action(description="Деактивировать выбранных пользователей")
def deactivate_users(modeladmin: UserAdmin, request: HttpRequest, queryset: QuerySet[User]) -> None:  # noqa: ARG001
    """Мягкое удаление: деактивирует пользователей без физического удаления из БД."""
    queryset.update(is_active=False)


@admin.action(description="Активировать выбранных пользователей")
def activate_users(modeladmin: UserAdmin, request: HttpRequest, queryset: QuerySet[User]) -> None:  # noqa: ARG001
    """Активирует ранее деактивированных пользователей."""
    queryset.update(is_active=True)


# Соответствие роли пользователя набору инлайнов на странице редактирования
_ROLE_INLINES: dict[str, list[type[InlineModelAdmin]]] = {
    Role.DOCTOR: [DoctorPatientsInline],
    Role.PATIENT: [PatientDoctorsInline, PatientCaregiversInline],
    Role.CAREGIVER: [CaregiverPatientsInline],
}


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

    actions: ClassVar = [deactivate_users, activate_users]

    def has_delete_permission(self, request: HttpRequest, obj: User | None = None) -> bool:  # noqa: ARG002
        """Запрещает физическое удаление пользователей, использует деактивацию."""
        return False

    def get_inlines(self, request: HttpRequest, obj: User | None) -> list[type[InlineModelAdmin]]:  # noqa: ARG002
        """Возвращает инлайны связей в зависимости от роли редактируемого пользователя."""
        if obj is None:
            return []
        return _ROLE_INLINES.get(obj.role, [])


admin.site.unregister(Group)
