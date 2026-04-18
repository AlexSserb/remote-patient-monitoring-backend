"""Сериализаторы для диагнозов."""

from __future__ import annotations

from typing import ClassVar

from rest_framework import serializers

from apps.diagnoses.models import Diagnosis, PatientDiagnosis


class DiagnosisShortSerializer(serializers.ModelSerializer):
    """Краткое представление диагноза для вложения в другие сериализаторы."""

    class Meta:
        """Метаданные сериализатора."""

        model = Diagnosis
        fields: ClassVar[list[str]] = ["id", "name", "code"]


class PatientDiagnosisSerializer(serializers.ModelSerializer):
    """Диагноз пациента с полями диагноза верхнего уровня для корректной генерации схемы."""

    id = serializers.IntegerField(source="diagnosis.id")
    name = serializers.CharField(source="diagnosis.name")
    code = serializers.CharField(source="diagnosis.code")

    class Meta:
        """Метаданные сериализатора."""

        model = PatientDiagnosis
        fields: ClassVar[list[str]] = ["id", "name", "code"]
