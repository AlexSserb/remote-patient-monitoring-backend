"""Регистрация моделей приложения diagnoses в Django Admin."""

from __future__ import annotations

from typing import ClassVar

from django.contrib import admin

from apps.diagnoses.models import (
    Diagnosis,
    DiagnosisMetric,
    DiaryEntry,
    DiaryEntryValue,
    Metric,
    PatientDiagnosis,
)


class DiagnosisMetricInline(admin.TabularInline):
    """Встроенное отображение метрик диагноза."""

    model = DiagnosisMetric
    extra = 0


@admin.register(Diagnosis)
class DiagnosisAdmin(admin.ModelAdmin):
    """Администрирование диагнозов с привязкой метрик."""

    list_display = ("code", "name")
    search_fields = ("code", "name")
    inlines: ClassVar = [DiagnosisMetricInline]


@admin.register(Metric)
class MetricAdmin(admin.ModelAdmin):
    """Администрирование метрик здоровья."""

    list_display = ("code", "name", "type", "unit")
    search_fields = ("code", "name")
    list_filter = ("type",)


@admin.register(PatientDiagnosis)
class PatientDiagnosisAdmin(admin.ModelAdmin):
    """Администрирование назначений диагнозов пациентам."""

    list_display = ("patient", "diagnosis", "assigned_by", "created_at")
    list_filter = ("diagnosis",)
    search_fields = ("patient__email", "diagnosis__code")


class DiaryEntryValueInline(admin.TabularInline):
    """Встроенное отображение значений метрик в дневниковой записи."""

    model = DiaryEntryValue
    extra = 0


@admin.register(DiaryEntry)
class DiaryEntryAdmin(admin.ModelAdmin):
    """Администрирование записей дневника пациентов."""

    list_display = ("patient", "created_at")
    list_filter = ("patient",)
    search_fields = ("patient__email",)
    inlines: ClassVar = [DiaryEntryValueInline]
