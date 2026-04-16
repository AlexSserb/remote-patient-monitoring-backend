"""Сериализаторы для представления чатов в зависимости от роли пользователя."""

from __future__ import annotations

from typing import ClassVar

from rest_framework import serializers

from apps.chats.models import Chat


class ChatItemSerializer(serializers.ModelSerializer):
    """Чат со сведениями о собеседнике — для плоского списка пациента."""

    interlocutor = serializers.SerializerMethodField()

    class Meta:
        """Метаданные сериализатора чата пациента."""

        model = Chat
        fields: ClassVar = ["id", "interlocutor", "last_message_at", "created_at"]

    def get_interlocutor(self, obj: Chat) -> dict:
        """Возвращает данные собеседника (не текущего пользователя)."""
        current_user_id: int = self.context["request"].user.pk
        other = next(
            (p for p in obj.participants.all() if p.pk != current_user_id),
            None,
        )
        if other is None:
            return {}
        return {
            "id": other.pk,
            "first_name": other.first_name,
            "last_name": other.last_name,
            "role": other.role,
        }


class ChatGroupMemberSerializer(serializers.Serializer):
    """Участник группы чатов с id чата и временем последнего сообщения."""

    id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    chat_id = serializers.IntegerField(allow_null=True)
    last_message_at = serializers.DateTimeField(allow_null=True)


class DoctorChatGroupSerializer(serializers.Serializer):
    """Группа чатов доктора — один пациент и все его опекуны."""

    patient = ChatGroupMemberSerializer()
    caregivers = ChatGroupMemberSerializer(many=True)


class CaregiverChatGroupSerializer(serializers.Serializer):
    """Группа чатов опекуна — один пациент, его доктора и другие опекуны."""

    patient = ChatGroupMemberSerializer()
    doctors = ChatGroupMemberSerializer(many=True)
    caregivers = ChatGroupMemberSerializer(many=True)
