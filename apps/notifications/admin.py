"""Регистрация моделей приложения notifications в Django Admin."""

from __future__ import annotations

from typing import ClassVar

from django.contrib import admin

from apps.notifications.models import (
    NotificationChannelConfig,
    NotificationRecord,
    NotificationSchedule,
)


@admin.register(NotificationSchedule)
class NotificationScheduleAdmin(admin.ModelAdmin):
    """Администрирование расписаний уведомлений."""

    list_display = ("recipient", "patient", "is_enabled", "days_of_week", "times", "updated_at")
    list_filter = ("is_enabled",)
    search_fields = ("recipient__email", "patient__email")


@admin.register(NotificationChannelConfig)
class NotificationChannelConfigAdmin(admin.ModelAdmin):
    """Администрирование конфигураций каналов уведомлений."""

    list_display = ("user", "channel", "is_active", "updated_at")
    list_filter = ("channel", "is_active")
    search_fields = ("user__email",)


class NotificationRecordInline(admin.TabularInline):
    """Встроенное отображение записей уведомлений в расписании."""

    model = NotificationRecord
    extra = 0
    fields = ("channel", "status", "reaction_score", "sent_at", "opened_at", "completed_at")
    readonly_fields = ("sent_at",)


@admin.register(NotificationRecord)
class NotificationRecordAdmin(admin.ModelAdmin):
    """Администрирование истории уведомлений."""

    list_display = ("recipient", "patient", "channel", "status", "reaction_score", "sent_at")
    list_filter = ("channel", "status")
    search_fields = ("recipient__email", "patient__email")
    readonly_fields: ClassVar = ["sent_at"]
