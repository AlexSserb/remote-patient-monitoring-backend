"""Сериализаторы для диагнозов."""

from __future__ import annotations

from typing import ClassVar

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.diagnoses.models import Diagnosis, DiaryEntry, DiaryEntryValue, Metric, PatientDiagnosis


class DiagnosisShortSerializer(serializers.ModelSerializer):
    """Краткое представление диагноза для вложения в другие сериализаторы."""

    class Meta:
        """Метаданные сериализатора."""

        model = Diagnosis
        fields: ClassVar[list[str]] = ["id", "name", "code"]


class DiaryFieldSerializer(serializers.ModelSerializer):
    """Поле дневника с агрегированными ограничениями по всем диагнозам пациента."""

    is_required = serializers.BooleanField()
    min_value = serializers.FloatField(allow_null=True)
    max_value = serializers.FloatField(allow_null=True)

    class Meta:
        """Метаданные сериализатора."""

        model = Metric
        fields: ClassVar[list[str]] = ["id", "name", "code", "unit", "type", "is_required", "min_value", "max_value"]


class DiaryEntryValueCreateSerializer(serializers.Serializer):
    """Значение одной метрики в создаваемой или обновляемой записи дневника."""

    metric_id = serializers.IntegerField()
    value_number = serializers.FloatField(allow_null=True, required=False, default=None)
    value_text = serializers.CharField(allow_blank=True, required=False, default="")
    value_boolean = serializers.BooleanField(allow_null=True, required=False, default=None)


class DiaryEntryCreateSerializer(serializers.Serializer):
    """Тело запроса для создания или обновления записи дневника."""

    values = DiaryEntryValueCreateSerializer(many=True)


class DiaryEntryValueInfo(serializers.ModelSerializer):
    """Значение метрики в составе ответа на запрос записи дневника."""

    metric_id = serializers.IntegerField(source="metric.id", read_only=True)
    metric_name = serializers.CharField(source="metric.name", read_only=True)
    metric_code = serializers.CharField(source="metric.code", read_only=True)
    metric_type = serializers.CharField(source="metric.type", read_only=True)
    metric_unit = serializers.CharField(source="metric.unit", read_only=True)

    class Meta:
        """Метаданные сериализатора."""

        model = DiaryEntryValue
        fields: ClassVar[list[str]] = [
            "metric_id",
            "metric_name",
            "metric_code",
            "metric_type",
            "metric_unit",
            "value_number",
            "value_text",
            "value_boolean",
        ]


class DiaryEntryAuthorInfo(serializers.ModelSerializer):
    """Автор записи дневника — пациент или опекун, создавший запись."""

    class Meta:
        """Метаданные сериализатора."""

        model = get_user_model()
        fields: ClassVar[list[str]] = ["id", "first_name", "last_name", "role"]


class DiaryEntryInfo(serializers.ModelSerializer):
    """Запись дневника с вложенными значениями метрик."""

    values = DiaryEntryValueInfo(many=True, read_only=True)
    author = DiaryEntryAuthorInfo(read_only=True)

    class Meta:
        """Метаданные сериализатора."""

        model = DiaryEntry
        fields: ClassVar[list[str]] = ["id", "created_at", "author", "values"]


class PatientDiagnosisSerializer(serializers.ModelSerializer):
    """Диагноз пациента с полями диагноза верхнего уровня для корректной генерации схемы."""

    id = serializers.IntegerField(source="diagnosis.id")
    name = serializers.CharField(source="diagnosis.name")
    code = serializers.CharField(source="diagnosis.code")

    class Meta:
        """Метаданные сериализатора."""

        model = PatientDiagnosis
        fields: ClassVar[list[str]] = ["id", "name", "code"]
