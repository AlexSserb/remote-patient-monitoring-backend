"""Конфигурация приложения системы уведомлений."""

from __future__ import annotations

from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """Конфигурация приложения notifications — расписания и история уведомлений."""

    name = "apps.notifications"
