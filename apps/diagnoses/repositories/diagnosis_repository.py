"""Репозиторий операций с диагнозами и дневниками пациентов."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db.models import BooleanField, FloatField, IntegerField, Max, Min
from django.db.models.functions import Cast
from django.shortcuts import get_object_or_404

from apps.diagnoses.models import Diagnosis, DiaryEntry, DiaryEntryValue, Metric, MetricType
from apps.users.models import CaregiverPatient, DoctorPatient, Role

if TYPE_CHECKING:
    import datetime

    from django.db.models import QuerySet


class DiagnosisRepository:
    """Репозиторий для всех операций с диагнозами, метриками и дневниковыми записями."""

    def list_diagnoses(self) -> QuerySet:
        """Возвращает все диагнозы, упорядоченные по коду."""
        return Diagnosis.objects.order_by("code")

    def has_caregiver_access(self, caregiver: Any, patient_id: int) -> bool:
        """Проверяет, прикреплён ли опекун к данному пациенту."""
        return CaregiverPatient.objects.filter(caregiver=caregiver, patient_id=patient_id).exists()

    def has_doctor_access(self, doctor: Any, patient_id: int) -> bool:
        """Проверяет, прикреплён ли доктор к данному пациенту."""
        return DoctorPatient.objects.filter(doctor=doctor, patient_id=patient_id).exists()

    def get_patient_by_id(self, patient_id: int) -> Any:
        """Возвращает пользователя с ролью пациента или бросает Http404."""
        from apps.users.models import User  # noqa: PLC0415

        return get_object_or_404(User, id=patient_id, role=Role.PATIENT)

    def get_diary_fields(self, patient: Any) -> QuerySet:
        """Возвращает уникальные метрики пациента с агрегированными ограничениями по всем его диагнозам."""
        return (
            Metric.objects.filter(diagnosis_metrics__diagnosis__patient_diagnoses__patient=patient)
            .annotate(
                is_required=Cast(
                    Max(Cast("diagnosis_metrics__is_required", output_field=IntegerField())),
                    output_field=BooleanField(),
                ),
                min_value=Max("diagnosis_metrics__min_value", output_field=FloatField()),
                max_value=Min("diagnosis_metrics__max_value", output_field=FloatField()),
            )
            .order_by("name")
        )

    def get_diary_entries(self, patient: Any) -> QuerySet:
        """Возвращает все записи дневника пациента с предзагруженными связями."""
        return DiaryEntry.objects.filter(patient=patient).select_related("author").prefetch_related("values__metric")

    def create_diary_entry(self, patient: Any, author: Any) -> DiaryEntry:
        """Создаёт новую запись дневника для указанного пациента и автора."""
        return DiaryEntry.objects.create(patient=patient, author=author)

    def bulk_create_values(self, entry: DiaryEntry, values: list[dict]) -> None:
        """Создаёт значения метрик для записи дневника пакетной вставкой."""
        DiaryEntryValue.objects.bulk_create(
            [
                DiaryEntryValue(
                    entry=entry,
                    metric_id=v["metric_id"],
                    value_number=v.get("value_number"),
                    value_text=v.get("value_text", ""),
                    value_boolean=v.get("value_boolean"),
                )
                for v in values
            ]
        )

    def get_entry_with_values(self, pk: int) -> DiaryEntry:
        """Возвращает запись дневника с предзагруженными значениями метрик и автором."""
        return DiaryEntry.objects.select_related("author").prefetch_related("values__metric").get(pk=pk)

    def get_entry_for_patient(self, pk: int, patient: Any) -> DiaryEntry:
        """Возвращает запись дневника, принадлежащую указанному пациенту, или бросает Http404."""
        return get_object_or_404(DiaryEntry, pk=pk, patient=patient)

    def upsert_entry_value(self, entry: DiaryEntry, metric_id: int, defaults: dict) -> None:
        """Обновляет или создаёт значение метрики в записи дневника."""
        DiaryEntryValue.objects.update_or_create(entry=entry, metric_id=metric_id, defaults=defaults)

    def delete_entry(self, entry: DiaryEntry) -> None:
        """Удаляет запись дневника вместе со всеми её значениями метрик."""
        entry.delete()

    def get_analytics_metrics(self, patient: Any) -> QuerySet:
        """Возвращает числовые метрики, доступные пациенту для отображения на графике."""
        return (
            Metric.objects.filter(
                diagnosis_metrics__diagnosis__patient_diagnoses__patient=patient,
                type=MetricType.NUMBER,
            )
            .distinct()
            .order_by("name")
        )

    def get_analytics_data_points(
        self,
        patient: Any,
        date_from: datetime.date,
        date_to: datetime.date,
        metric_ids: list[int],
    ) -> QuerySet:
        """Возвращает числовые значения метрик пациента за указанный период."""
        return (
            DiaryEntryValue.objects.filter(
                entry__patient=patient,
                entry__created_at__date__gte=date_from,
                entry__created_at__date__lte=date_to,
                metric_id__in=metric_ids,
                metric__type=MetricType.NUMBER,
                value_number__isnull=False,
            )
            .select_related("metric", "entry")
            .order_by("entry__created_at")
        )
