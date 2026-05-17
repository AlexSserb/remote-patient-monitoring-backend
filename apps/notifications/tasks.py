"""Задачи Celery для отправки уведомлений пользователям."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from celery import shared_task

from apps.notifications.services.notification_dispatch_service import NotificationDispatchService

logger = logging.getLogger(__name__)


@shared_task
def scan_and_dispatch() -> None:
    """Находит расписания, совпадающие с текущим временем, и запускает задачи отправки."""
    now_utc = datetime.now(tz=UTC)
    logger.info("scan_and_dispatch: starting at %s", now_utc.strftime("%Y-%m-%d %H:%M UTC"))
    service = NotificationDispatchService()
    schedule_ids = service.get_due_schedule_ids(now_utc)
    for schedule_id in schedule_ids:
        send_notification.delay(schedule_id)
    logger.info("scan_and_dispatch: dispatched %d tasks", len(schedule_ids))


@shared_task
def send_notification(schedule_id: int) -> None:
    """Отправляет уведомление по всем активным каналам получателя и создаёт записи истории."""
    logger.info("send_notification: starting for schedule %s", schedule_id)
    service = NotificationDispatchService()
    record_ids = service.send_for_schedule(schedule_id)
    for record_id in record_ids:
        mark_ignored.apply_async(args=[record_id], countdown=86_400)
    logger.info("send_notification: schedule %s done, %d records created", schedule_id, len(record_ids))


@shared_task
def mark_ignored(record_id: int) -> None:
    """Переводит уведомление в статус 'проигнорировано', если пользователь его не открыл."""
    logger.info("mark_ignored: processing record %s", record_id)
    NotificationDispatchService().mark_record_ignored(record_id)
