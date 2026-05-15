"""Сервис диспетчеризации и отправки уведомлений по каналам."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.mail import send_mail
from pywebpush import WebPushException, webpush

from apps.notifications.models import NotificationChannel, NotificationSchedule
from apps.notifications.repositories import ChannelConfigRepository, NotificationRecordRepository, ScheduleRepository

logger = logging.getLogger(__name__)


class NotificationDispatchService:
    """Диспетчеризация и отправка уведомлений: выборка расписаний и рассылка по каналам."""

    def __init__(
        self,
        schedule_repo: ScheduleRepository | None = None,
        config_repo: ChannelConfigRepository | None = None,
        record_repo: NotificationRecordRepository | None = None,
    ) -> None:
        """Инициализирует сервис с переданными или дефолтными репозиториями."""
        self._schedule_repo = schedule_repo or ScheduleRepository()
        self._config_repo = config_repo or ChannelConfigRepository()
        self._record_repo = record_repo or NotificationRecordRepository()

    def get_due_schedule_ids(self, now_utc: datetime) -> list[int]:
        """Возвращает PK расписаний, совпадающих с текущим временем в часовом поясе получателя."""
        schedules = list(self._schedule_repo.get_active_schedules())
        logger.info("scan_and_dispatch: checking %d active schedules", len(schedules))
        due: list[int] = []
        for schedule in schedules:
            tz = self._resolve_tz(schedule.recipient.timezone)
            local_now = now_utc.astimezone(tz)
            if local_now.weekday() not in schedule.days_of_week:
                continue
            if local_now.strftime("%H:%M") not in [t.strftime("%H:%M") for t in schedule.times]:
                continue
            # Защита от повторной отправки при двойном срабатывании Beat в одну минуту
            if self._record_repo.has_recent_notification(schedule, now_utc - timedelta(minutes=2)):
                logger.debug("scan_and_dispatch: schedule %s skipped — already sent recently", schedule.pk)
                continue
            due.append(schedule.pk)
        logger.info("scan_and_dispatch: %d schedules due for dispatch", len(due))
        return due

    def send_for_schedule(self, schedule_id: int) -> list[int]:
        """Отправляет уведомление по всем активным каналам получателя; возвращает PK созданных записей."""
        try:
            schedule = self._schedule_repo.get_enabled_by_id(schedule_id)
        except NotificationSchedule.DoesNotExist:
            logger.warning("send_notification: schedule %s not found or disabled", schedule_id)
            return []

        configs = list(self._config_repo.get_active_configs_for_user(schedule.recipient))
        patient_name: str = schedule.patient.get_full_name()
        logger.info(
            "send_notification: schedule=%s recipient=%s patient=%r channels=%d",
            schedule_id,
            schedule.recipient_id,  # ty: ignore[unresolved-attribute]
            patient_name,
            len(configs),
        )

        record_ids: list[int] = []
        for config in configs:
            target: str
            try:
                if config.channel == NotificationChannel.EMAIL:
                    # config может переопределять адрес; иначе берём email аккаунта
                    email: str = config.config.get("email") or schedule.recipient.email
                    self._send_email(email, patient_name)
                    target = email
                elif config.channel == NotificationChannel.WEB_PUSH:
                    subscription: dict = config.config
                    if not subscription.get("endpoint"):
                        continue
                    self._send_web_push(subscription, patient_name)
                    target = subscription["endpoint"]
                else:
                    continue
            except Exception:
                logger.exception(
                    "Failed to send %s notification for schedule %s",
                    config.channel,
                    schedule_id,
                )
                continue

            record = self._record_repo.create_record(schedule, config.channel, target)
            record_ids.append(record.pk)
            logger.info(
                "send_notification: sent %s → %s (record=%s)",
                config.channel,
                target,
                record.pk,
            )

        return record_ids

    def mark_record_ignored(self, record_id: int) -> None:
        """Переводит запись уведомления в статус 'проигнорировано'."""
        self._record_repo.mark_ignored(record_id)

    @staticmethod
    def _resolve_tz(timezone_str: str) -> ZoneInfo:
        """Возвращает объект часового пояса или UTC при невалидном значении."""
        try:
            return ZoneInfo(timezone_str)
        except ZoneInfoNotFoundError, KeyError:
            return ZoneInfo("UTC")

    @staticmethod
    def _send_email(recipient_email: str, patient_name: str) -> None:
        """Отправляет email-напоминание о необходимости заполнить дневник здоровья."""
        send_mail(
            subject="Напоминание о заполнении дневника",
            message=f"Пожалуйста, заполните дневник здоровья пациента {patient_name}.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
        )

    @staticmethod
    def _send_web_push(subscription: dict, patient_name: str) -> None:
        """Отправляет web push уведомление через протокол Web Push с VAPID-подписью."""
        payload = json.dumps(
            {
                "title": "Напоминание о дневнике",
                "body": f"Заполните дневник здоровья пациента {patient_name}.",
                "url": "/",
            },
            ensure_ascii=False,
        )
        try:
            webpush(
                subscription_info=subscription,
                data=payload,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": f"mailto:{settings.VAPID_CLAIMS_EMAIL}"},
            )
        except WebPushException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", "?")
            logger.exception("Web push failed (status %s)", status_code)
            raise
