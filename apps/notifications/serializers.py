"""Сериализаторы системы уведомлений."""

from __future__ import annotations

from typing import ClassVar

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.notifications.models import NotificationSchedule

UserModel = get_user_model()


class RecipientBriefSerializer(serializers.ModelSerializer):
    """Краткое представление получателя уведомления для вложенных ответов."""

    class Meta:
        """Метаданные сериализатора."""

        model = UserModel
        fields: ClassVar[list[str]] = ["id", "first_name", "last_name", "role"]


class NotificationScheduleSerializer(serializers.ModelSerializer):
    """Расписание уведомлений с вложенными данными получателя для чтения."""

    recipient = RecipientBriefSerializer(read_only=True)
    days_of_week = serializers.ListField(child=serializers.IntegerField(), read_only=True)
    times = serializers.ListField(
        child=serializers.TimeField(format="%H:%M"),
        read_only=True,
    )

    class Meta:
        """Метаданные сериализатора."""

        model = NotificationSchedule
        fields: ClassVar[list[str]] = [
            "id",
            "recipient",
            "days_of_week",
            "times",
            "is_enabled",
            "updated_at",
        ]


class NotificationScheduleCreateSerializer(serializers.Serializer):
    """Сериализатор создания расписания уведомлений: проверяет пациента и параметры расписания."""

    patient_id = serializers.IntegerField()
    recipient_id = serializers.IntegerField(required=False)
    days_of_week = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6),
        allow_empty=True,
    )
    times = serializers.ListField(
        child=serializers.TimeField(format="%H:%M", input_formats=["%H:%M", "%H:%M:%S"]),
        allow_empty=True,
    )
    is_enabled = serializers.BooleanField(default=True)

    def validate_patient_id(self, value: int) -> int:
        """Проверяет существование пользователя с ролью пациента."""
        from apps.users.models import Role  # noqa: PLC0415

        if not UserModel.objects.filter(pk=value, role=Role.PATIENT).exists():
            msg = "Patient not found."
            raise serializers.ValidationError(msg)
        return value


class NotificationScheduleUpdateSerializer(serializers.Serializer):
    """Сериализатор обновления расписания: дни недели, время и признак активности."""

    days_of_week = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6),
        required=False,
        allow_empty=True,
    )
    times = serializers.ListField(
        child=serializers.TimeField(format="%H:%M", input_formats=["%H:%M", "%H:%M:%S"]),
        required=False,
        allow_empty=True,
    )
    is_enabled = serializers.BooleanField(required=False)
