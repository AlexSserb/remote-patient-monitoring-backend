"""Модели диагнозов, метрик и дневников пациентов."""

from __future__ import annotations

from typing import ClassVar

from django.conf import settings
from django.db import models

from apps.users.models import Role


class MetricType(models.TextChoices):
    """Типы значений метрики для дневниковых записей."""

    NUMBER = "number", "Число"
    BOOLEAN = "boolean", "Да/Нет"
    TEXT = "text", "Текст"


class Diagnosis(models.Model):
    """Медицинский диагноз, используемый для группировки метрик наблюдения."""

    name = models.CharField(max_length=255, verbose_name="Название")
    code = models.CharField(max_length=50, unique=True, verbose_name="Код (МКБ)")
    description = models.TextField(blank=True, verbose_name="Описание")

    class Meta:
        """Метаданные модели диагноза."""

        verbose_name = "Диагноз"
        verbose_name_plural = "Диагнозы"

    def __str__(self) -> str:
        """Возвращает строковое представление диагноза в виде кода и названия."""
        return f"{self.code} — {self.name}"


class PatientDiagnosis(models.Model):
    """Назначение диагноза конкретному пациенту лечащим врачом."""

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="diagnoses",
        limit_choices_to={"role": Role.PATIENT},
        verbose_name="Пациент",
    )
    diagnosis = models.ForeignKey(
        Diagnosis,
        on_delete=models.CASCADE,
        related_name="patient_diagnoses",
        verbose_name="Диагноз",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="assigned_diagnoses",
        limit_choices_to={"role": Role.DOCTOR},
        verbose_name="Назначил",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата назначения")

    class Meta:
        """Метаданные модели назначения диагноза."""

        verbose_name = "Диагноз пациента"
        verbose_name_plural = "Диагнозы пациентов"
        unique_together = ("patient", "diagnosis")

    def __str__(self) -> str:
        """Возвращает строковое представление назначения диагноза."""
        return f"{self.patient} — {self.diagnosis}"


class Metric(models.Model):
    """Показатель здоровья, отслеживаемый в дневнике пациента."""

    name = models.CharField(max_length=255, verbose_name="Название")
    code = models.CharField(max_length=50, unique=True, verbose_name="Код")
    unit = models.CharField(max_length=50, blank=True, verbose_name="Единица измерения")
    type = models.CharField(
        max_length=50,
        choices=MetricType.choices,
        verbose_name="Тип значения",
    )

    class Meta:
        """Метаданные модели метрики."""

        verbose_name = "Метрика"
        verbose_name_plural = "Метрики"

    def __str__(self) -> str:
        """Возвращает строковое представление метрики."""
        return f"{self.name} ({self.unit})" if self.unit else self.name


class DiagnosisMetric(models.Model):
    """Привязка метрики к диагнозу с параметрами допустимых значений."""

    diagnosis = models.ForeignKey(
        Diagnosis,
        on_delete=models.CASCADE,
        related_name="metrics",
        verbose_name="Диагноз",
    )
    metric = models.ForeignKey(
        Metric,
        on_delete=models.CASCADE,
        related_name="diagnosis_metrics",
        verbose_name="Метрика",
    )
    is_required = models.BooleanField(default=False, verbose_name="Обязательная")
    min_value = models.FloatField(null=True, blank=True, verbose_name="Минимум")
    max_value = models.FloatField(null=True, blank=True, verbose_name="Максимум")

    class Meta:
        """Метаданные модели привязки метрики к диагнозу."""

        verbose_name = "Метрика диагноза"
        verbose_name_plural = "Метрики диагнозов"
        unique_together = ("diagnosis", "metric")

    def __str__(self) -> str:
        """Возвращает строковое представление привязки метрики к диагнозу."""
        return f"{self.diagnosis.code} / {self.metric.code}"


class DiaryEntry(models.Model):
    """Запись в дневнике самонаблюдения пациента за один момент времени."""

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="diary_entries",
        limit_choices_to={"role": Role.PATIENT},
        verbose_name="Пациент",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата записи")

    class Meta:
        """Метаданные модели записи дневника."""

        verbose_name = "Запись дневника"
        verbose_name_plural = "Записи дневника"
        ordering: ClassVar = ["-created_at"]
        indexes: ClassVar = [
            # основной паттерн запроса: все записи пациента в хронологии
            models.Index(fields=["patient", "-created_at"], name="diaryentry_patient_date_idx"),
        ]

    def __str__(self) -> str:
        """Возвращает строковое представление записи дневника."""
        return f"DiaryEntry(patient={self.patient_id}, created_at={self.created_at})"  # ty: ignore[unresolved-attribute]


class DiaryEntryValue(models.Model):
    """Значение конкретной метрики в рамках одной дневниковой записи."""

    entry = models.ForeignKey(
        DiaryEntry,
        on_delete=models.CASCADE,
        related_name="values",
        verbose_name="Запись",
    )
    metric = models.ForeignKey(
        Metric,
        on_delete=models.CASCADE,
        related_name="diary_values",
        verbose_name="Метрика",
    )
    value_number = models.FloatField(null=True, blank=True, verbose_name="Числовое значение")
    value_text = models.TextField(blank=True, verbose_name="Текстовое значение")
    value_boolean = models.BooleanField(null=True, blank=True, verbose_name="Булево значение")

    class Meta:
        """Метаданные модели значения метрики в дневнике."""

        verbose_name = "Значение метрики"
        verbose_name_plural = "Значения метрик"
        unique_together = ("entry", "metric")

    def __str__(self) -> str:
        """Возвращает строковое представление значения метрики."""
        return f"DiaryEntryValue(entry={self.entry_id}, metric={self.metric.code})"  # ty: ignore[unresolved-attribute]
