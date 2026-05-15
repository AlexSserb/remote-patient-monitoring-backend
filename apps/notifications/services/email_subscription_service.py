"""Сервис управления email-уведомлениями пользователей."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from rest_framework.exceptions import PermissionDenied

from apps.notifications.repositories import ChannelConfigRepository, ScheduleRepository


class EmailSubscriptionService:
    """Управление email-уведомлениями пользователей через канал NotificationChannel.EMAIL."""

    def __init__(
        self,
        repo: ChannelConfigRepository | None = None,
        schedule_repo: ScheduleRepository | None = None,
    ) -> None:
        """Инициализирует сервис с переданными или дефолтными репозиториями."""
        self._repo = repo or ChannelConfigRepository()
        self._schedule_repo = schedule_repo or ScheduleRepository()

    def resolve_target(self, requester: Any, target_user_id: int | None) -> Any:
        """Возвращает целевого пользователя; проверяет доступ, если цель — не сам запрашивающий."""
        if target_user_id is None or target_user_id == requester.pk:
            return requester
        try:
            target = self._schedule_repo.get_patient(target_user_id)
        except ObjectDoesNotExist as e:
            raise Http404 from e
        if not (
            self._schedule_repo.has_caregiver_access(requester, target_user_id)
            or self._schedule_repo.has_doctor_access(requester, target_user_id)
        ):
            raise PermissionDenied
        return target

    def get_status(self, user: Any) -> bool:
        """Возвращает True, если email-уведомления включены для пользователя."""
        return self._repo.get_email_is_active(user)

    def enable(self, user: Any) -> None:
        """Включает email-уведомления; при отсутствии конфига создаёт новый."""
        self._repo.enable_email_subscription(user)

    def disable(self, user: Any) -> None:
        """Отключает email-уведомления без удаления конфига из базы."""
        self._repo.disable_email_subscription(user)
