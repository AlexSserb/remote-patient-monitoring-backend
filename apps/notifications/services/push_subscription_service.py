"""Сервис управления web push подписками пользователей."""

from __future__ import annotations

from typing import Any

from apps.notifications.repositories import ChannelConfigRepository


class PushSubscriptionService:
    """Управление web push подписками пользователей."""

    def __init__(self, repo: ChannelConfigRepository | None = None) -> None:
        """Инициализирует сервис с переданным или дефолтным репозиторием."""
        self._repo = repo or ChannelConfigRepository()

    def save_subscription(self, user: Any, config: dict) -> None:
        """Сохраняет или обновляет push-подписку браузера для пользователя."""
        self._repo.upsert_push_subscription(user, config)

    def remove_subscription(self, user: Any) -> None:
        """Деактивирует push-подписку пользователя без физического удаления."""
        self._repo.deactivate_push_subscription(user)
