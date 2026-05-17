"""Репозиторий записей истории отправленных уведомлений."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apps.notifications.models import NotificationRecord, NotificationStatus

if TYPE_CHECKING:
    from datetime import datetime

    from apps.notifications.models import NotificationSchedule


class NotificationRecordRepository:
    """Репозиторий создания и обновления записей истории уведомлений."""

    def has_recent_notification(self, schedule: NotificationSchedule, since: datetime) -> bool:
        """Возвращает True, если уведомление по расписанию уже отправлялось после указанного момента."""
        return NotificationRecord.objects.filter(
            schedule=schedule,
            sent_at__gte=since,
        ).exists()

    def create_record(
        self,
        schedule: NotificationSchedule,
        channel: str,
        target: str,
    ) -> NotificationRecord:
        """Создаёт запись об успешно отправленном уведомлении с денормализованными recipient и patient."""
        return NotificationRecord.objects.create(
            schedule=schedule,
            recipient=schedule.recipient,
            patient=schedule.patient,
            channel=channel,
            channel_target=target,
            status=NotificationStatus.SENT,
        )

    def mark_ignored(self, record_id: int) -> None:
        """Переводит запись уведомления в статус 'проигнорировано', если пользователь её не открыл."""
        NotificationRecord.objects.filter(
            pk=record_id,
            status=NotificationStatus.SENT,
        ).update(status=NotificationStatus.IGNORED)
