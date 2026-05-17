"""Репозиторий конфигураций каналов доставки уведомлений."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apps.notifications.models import NotificationChannel, NotificationChannelConfig

if TYPE_CHECKING:
    from django.db.models import QuerySet


class ChannelConfigRepository:
    """Репозиторий конфигураций каналов доставки уведомлений."""

    def upsert_push_subscription(self, user: Any, config: dict) -> None:
        """Создаёт или обновляет активную web push подписку пользователя."""
        NotificationChannelConfig.objects.update_or_create(
            user=user,
            channel=NotificationChannel.WEB_PUSH,
            defaults={"config": config, "is_active": True},
        )

    def deactivate_push_subscription(self, user: Any) -> None:
        """Деактивирует web push подписку пользователя без удаления записи."""
        NotificationChannelConfig.objects.filter(
            user=user,
            channel=NotificationChannel.WEB_PUSH,
        ).update(is_active=False)

    def get_email_is_active(self, user: Any) -> bool:
        """Возвращает True, если email-канал уведомлений активен для пользователя."""
        config = NotificationChannelConfig.objects.filter(
            user=user,
            channel=NotificationChannel.EMAIL,
        ).first()
        return bool(config and config.is_active)

    def enable_email_subscription(self, user: Any) -> None:
        """Создаёт или активирует email-канал уведомлений для пользователя."""
        NotificationChannelConfig.objects.update_or_create(
            user=user,
            channel=NotificationChannel.EMAIL,
            defaults={"config": {}, "is_active": True},
        )

    def get_active_configs_for_user(self, user: Any) -> QuerySet[NotificationChannelConfig]:
        """Возвращает все активные конфигурации каналов пользователя."""
        return NotificationChannelConfig.objects.filter(user=user, is_active=True)

    def disable_email_subscription(self, user: Any) -> None:
        """Деактивирует email-канал уведомлений пользователя без удаления записи."""
        NotificationChannelConfig.objects.filter(
            user=user,
            channel=NotificationChannel.EMAIL,
        ).update(is_active=False)
