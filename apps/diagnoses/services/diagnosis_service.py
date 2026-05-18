"""Сервис бизнес-логики диагнозов и дневника пациентов."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.diagnoses.repositories import DiagnosisRepository
from apps.users.models import Role

if TYPE_CHECKING:
    import datetime

    from django.db.models import QuerySet


class DiagnosisService:
    """Сервис для работы с диагнозами, полями дневника, записями дневника и аналитикой."""

    def __init__(self, repo: DiagnosisRepository | None = None) -> None:
        """Инициализирует сервис с переданным или дефолтным репозиторием."""
        self._repo = repo or DiagnosisRepository()

    def list_diagnoses(self) -> QuerySet:
        """Возвращает все диагнозы системы."""
        return self._repo.list_diagnoses()

    # ------------------------------------------------------------------
    # Вспомогательные методы разрешения пациента по роли
    # ------------------------------------------------------------------

    def _resolve_diary_patient(self, user: Any, patient_id_raw: str | None) -> Any:
        """Определяет пациента для доступа к дневнику; доктор не имеет права доступа."""
        if user.role == Role.PATIENT:
            return user
        if user.role == Role.CAREGIVER:
            return self._resolve_patient_with_caregiver_check(user, patient_id_raw)
        raise PermissionDenied

    def _resolve_analytics_patient(self, user: Any, patient_id: int | None) -> Any:
        """Определяет пациента для аналитики; доктор и опекун обязаны передать patient_id."""
        if user.role == Role.PATIENT:
            return user
        if patient_id is None:
            raise ValidationError({"patient_id": "patient_id is required"})
        if user.role == Role.CAREGIVER:
            if not self._repo.has_caregiver_access(user, patient_id):
                raise PermissionDenied
            return self._repo.get_patient_by_id(patient_id)
        if user.role == Role.DOCTOR:
            if not self._repo.has_doctor_access(user, patient_id):
                raise PermissionDenied
            return self._repo.get_patient_by_id(patient_id)
        raise PermissionDenied

    def _resolve_patient_with_caregiver_check(self, caregiver: Any, patient_id_raw: str | None) -> Any:
        """Парсит patient_id и проверяет доступ опекуна к пациенту."""
        patient_id = self._parse_patient_id(patient_id_raw)
        if not self._repo.has_caregiver_access(caregiver, patient_id):
            raise PermissionDenied
        return self._repo.get_patient_by_id(patient_id)

    @staticmethod
    def _parse_patient_id(patient_id_raw: str | None) -> int:
        """Проверяет наличие и формат patient_id; бросает ValidationError при ошибке."""
        if not patient_id_raw:
            raise ValidationError({"patient_id": "patient_id is required"})
        try:
            return int(patient_id_raw)
        except ValueError:
            raise ValidationError({"patient_id": "patient_id must be an integer"}) from None

    # ------------------------------------------------------------------
    # Поля дневника
    # ------------------------------------------------------------------

    def get_diary_fields(self, user: Any, patient_id_raw: str | None) -> QuerySet:
        """Возвращает метрики дневника для пациента или подопечного опекуна."""
        patient = self._resolve_diary_patient(user, patient_id_raw)
        return self._repo.get_diary_fields(patient)

    # ------------------------------------------------------------------
    # Записи дневника
    # ------------------------------------------------------------------

    def list_diary_entries(self, user: Any, patient_id_raw: str | None) -> QuerySet:
        """Возвращает все записи дневника пациента в обратном хронологическом порядке."""
        patient = self._resolve_diary_patient(user, patient_id_raw)
        return self._repo.get_diary_entries(patient)

    def create_diary_entry(self, user: Any, patient_id_raw: str | None, data: dict) -> Any:
        """Создаёт новую запись дневника с переданным набором значений метрик."""
        patient = self._resolve_diary_patient(user, patient_id_raw)
        entry = self._repo.create_diary_entry(patient, author=user)
        self._repo.bulk_create_values(entry, data["values"])
        return self._repo.get_entry_with_values(entry.pk)

    def update_diary_entry(self, user: Any, patient_id_raw: str | None, entry_pk: int, data: dict) -> Any:
        """Обновляет значения метрик в существующей записи дневника через upsert."""
        patient = self._resolve_diary_patient(user, patient_id_raw)
        entry = self._repo.get_entry_for_patient(entry_pk, patient)
        for v in data["values"]:
            self._repo.upsert_entry_value(
                entry,
                v["metric_id"],
                {
                    "value_number": v.get("value_number"),
                    "value_text": v.get("value_text", ""),
                    "value_boolean": v.get("value_boolean"),
                },
            )
        return self._repo.get_entry_with_values(entry.pk)

    def delete_diary_entry(self, user: Any, patient_id_raw: str | None, entry_pk: int) -> None:
        """Удаляет запись дневника, проверяя принадлежность пациенту."""
        patient = self._resolve_diary_patient(user, patient_id_raw)
        entry = self._repo.get_entry_for_patient(entry_pk, patient)
        self._repo.delete_entry(entry)

    # ------------------------------------------------------------------
    # Аналитика
    # ------------------------------------------------------------------

    def get_analytics(
        self,
        user: Any,
        patient_id: int | None,
        date_from: datetime.date,
        date_to: datetime.date,
        metric_ids: list[int],
    ) -> tuple[Any, Any]:
        """Возвращает доступные метрики и точки данных пациента за указанный период."""
        patient = self._resolve_analytics_patient(user, patient_id)
        available_metrics = self._repo.get_analytics_metrics(patient)
        data_points = (
            self._repo.get_analytics_data_points(patient, date_from, date_to, metric_ids) if metric_ids else []
        )
        return available_metrics, data_points
