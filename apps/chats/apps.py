"""Конфигурация приложения чатов."""

from __future__ import annotations

from django.apps import AppConfig


class ChatsConfig(AppConfig):
    """Конфигурация приложения chats — прямые чаты между участниками системы."""

    name = "apps.chats"

    def ready(self) -> None:
        """Подключает обработчики сигналов при старте приложения."""
        import apps.chats.signals  # noqa: F401, PLC0415
