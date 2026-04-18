"""Конфигурация приложения диагнозов и дневников пациентов."""

from __future__ import annotations

from django.apps import AppConfig


class DiagnosesConfig(AppConfig):
    """Конфигурация приложения diagnoses — диагнозы, метрики и дневники пациентов."""

    name = "apps.diagnoses"
