"""Сервис управления расписаниями уведомлений."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.notifications.repositories import ScheduleRepository
from apps.users.models import Role

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.notifications.models import NotificationSchedule


class ScheduleService:
    """Управление расписаниями уведомлений с проверкой прав доступа."""

    def __init__(self, repo: ScheduleRepository | None = None) -> None:
        """Инициализирует сервис с переданным или дефолтным репозиторием."""
        self._repo = repo or ScheduleRepository()

    def list_schedules(self, user: Any, patient_id: int) -> QuerySet[NotificationSchedule]:
        """Возвращает расписания для пациента, видимые текущему пользователю."""
        try:
            patient = self._repo.get_patient(patient_id)
        except ObjectDoesNotExist as e:
            raise Http404 from e
        self._check_patient_access(user, patient)
        qs = self._repo.get_for_patient(patient)
        return self._repo.filter_for_user(qs, user, patient)

    def upsert_schedule(self, user: Any, data: dict) -> tuple[NotificationSchedule, bool]:
        """Создаёт или обновляет расписание, определяя получателя по роли пользователя."""
        try:
            patient = self._repo.get_patient(data["patient_id"])
        except ObjectDoesNotExist as e:
            raise Http404 from e
        self._check_patient_access(user, patient)
        recipient = self._resolve_recipient(user, patient, data.get("recipient_id"))
        schedule_data = {
            "days_of_week": data["days_of_week"],
            "times": data["times"],
            "is_enabled": data["is_enabled"],
        }
        return self._repo.upsert(recipient, patient, schedule_data)

    def patch_schedule(self, user: Any, schedule_id: int, data: dict) -> NotificationSchedule:
        """Частично обновляет поля расписания при наличии прав на редактирование."""
        try:
            schedule = self._repo.get_by_id(schedule_id)
        except ObjectDoesNotExist as e:
            raise Http404 from e
        if not self._can_edit(user, schedule):
            raise PermissionDenied
        for field, value in data.items():
            setattr(schedule, field, value)
        self._repo.save(schedule)
        return schedule

    def _check_patient_access(self, user: Any, patient: Any) -> None:
        """Проверяет право просмотра расписаний пациента по роли, бросает PermissionDenied."""
        if user.role == Role.PATIENT:
            if user.pk != patient.pk:
                raise PermissionDenied
        elif user.role == Role.CAREGIVER:
            if not self._repo.has_caregiver_access(user, patient.pk):
                raise PermissionDenied
        elif user.role == Role.DOCTOR:
            if not self._repo.has_doctor_access(user, patient.pk):
                raise PermissionDenied
        else:
            raise PermissionDenied

    def _can_edit(self, user: Any, schedule: NotificationSchedule) -> bool:
        """Проверяет право редактировать расписание по роли и связям пользователя."""
        patient_id = schedule.patient_id  # ty: ignore[unresolved-attribute]
        if user.role == Role.PATIENT:
            return (  # ty: ignore[unresolved-attribute]
                user.pk == schedule.recipient_id and user.pk == patient_id
            )
        if user.role == Role.CAREGIVER:
            return self._repo.has_caregiver_access(user, patient_id)
        if user.role == Role.DOCTOR:
            return self._repo.has_doctor_access(user, patient_id)
        return False

    def _resolve_recipient(self, user: Any, patient: Any, recipient_id: int | None) -> Any:
        """Определяет получателя расписания: себя или пациента, с проверкой прав роли."""
        if recipient_id is not None and recipient_id != user.pk:
            if recipient_id != patient.pk:
                raise ValidationError({"detail": "recipient_id must be patient or self."})
            if user.role == Role.PATIENT:
                raise PermissionDenied
            return patient
        if user.role == Role.DOCTOR:
            raise ValidationError({"detail": "Doctors must specify recipient_id."})
        if user.role == Role.PATIENT and user.pk != patient.pk:
            raise PermissionDenied
        return user
