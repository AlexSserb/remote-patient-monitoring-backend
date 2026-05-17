"""Репозиторий расписаний уведомлений и проверок прав доступа."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.notifications.models import NotificationSchedule
from apps.users.models import CaregiverPatient, DoctorPatient, Role

if TYPE_CHECKING:
    from django.db.models import QuerySet

UserModel = get_user_model()


class ScheduleRepository:
    """Репозиторий расписаний уведомлений и проверок прав доступа к пациентам."""

    def get_patient(self, patient_id: int) -> Any:
        """Возвращает пользователя с ролью пациента или бросает DoesNotExist."""
        return UserModel.objects.get(pk=patient_id, role=Role.PATIENT)

    def get_for_patient(self, patient: Any) -> QuerySet[NotificationSchedule]:
        """Возвращает все расписания для пациента с предзагрузкой получателя."""
        return NotificationSchedule.objects.filter(patient=patient).select_related("recipient")

    def filter_for_user(
        self,
        qs: QuerySet[NotificationSchedule],
        user: Any,
        patient: Any,
    ) -> QuerySet[NotificationSchedule]:
        """Фильтрует расписания по роли: доктор видит все, опекун — своё и пациента, пациент — своё."""
        if user.role == Role.DOCTOR:
            return qs
        if user.role == Role.CAREGIVER:
            return qs.filter(Q(recipient=user) | Q(recipient=patient))
        return qs.filter(recipient=user)

    def get_by_id(self, schedule_id: int) -> NotificationSchedule:
        """Возвращает расписание по PK с предзагруженными связями или бросает DoesNotExist."""
        return NotificationSchedule.objects.select_related("recipient", "patient").get(pk=schedule_id)

    def upsert(self, recipient: Any, patient: Any, data: dict) -> tuple[NotificationSchedule, bool]:
        """Создаёт расписание или обновляет существующее; возвращает (объект, флаг_создания)."""
        return NotificationSchedule.objects.update_or_create(
            recipient=recipient,
            patient=patient,
            defaults=data,
        )

    def save(self, schedule: NotificationSchedule) -> None:
        """Сохраняет изменения расписания в базе данных."""
        schedule.save()

    def get_active_schedules(self) -> QuerySet[NotificationSchedule]:
        """Возвращает все включённые расписания с предзагрузкой получателя и пациента."""
        return NotificationSchedule.objects.filter(is_enabled=True).select_related(
            "recipient",
            "patient",
        )

    def get_enabled_by_id(self, schedule_id: int) -> NotificationSchedule:
        """Возвращает включённое расписание по PK с предзагруженными связями или бросает DoesNotExist."""
        return NotificationSchedule.objects.select_related("recipient", "patient").get(
            pk=schedule_id,
            is_enabled=True,
        )

    def has_caregiver_access(self, caregiver: Any, patient_id: int) -> bool:
        """Проверяет наличие связи опекун-пациент в базе данных."""
        return CaregiverPatient.objects.filter(caregiver=caregiver, patient_id=patient_id).exists()

    def has_doctor_access(self, doctor: Any, patient_id: int) -> bool:
        """Проверяет наличие связи доктор-пациент в базе данных."""
        return DoctorPatient.objects.filter(doctor=doctor, patient_id=patient_id).exists()
