"""Сериализаторы для представления чатов в зависимости от роли пользователя."""

from __future__ import annotations

from typing import ClassVar

from rest_framework import serializers

from apps.chats.models import Chat, Message


class LastMessagePreviewSerializer(serializers.Serializer):
    """Превью последнего сообщения для отображения в списке чатов."""

    content = serializers.CharField()
    sender_name = serializers.CharField()


class ChatItemSerializer(serializers.ModelSerializer):
    """Чат со сведениями о собеседнике — для плоского списка пациента."""

    interlocutor = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        """Метаданные сериализатора чата пациента."""

        model = Chat
        fields: ClassVar = ["id", "interlocutor", "last_message", "last_message_at", "created_at"]

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

    def get_last_message(self, obj: Chat) -> dict | None:
        """Возвращает превью последнего сообщения из аннотаций запроса."""
        content = getattr(obj, "_lm_content", None)
        if not content:
            return None
        sender_name = f"{getattr(obj, '_lm_sender_first', '')} {getattr(obj, '_lm_sender_last', '')}".strip()
        return {"content": content, "sender_name": sender_name}


class ChatGroupMemberSerializer(serializers.Serializer):
    """Участник группы чатов с id чата, временем и превью последнего сообщения."""

    id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    chat_id = serializers.IntegerField(allow_null=True)
    last_message_at = serializers.DateTimeField(allow_null=True)
    last_message = LastMessagePreviewSerializer(allow_null=True)


class DoctorChatGroupSerializer(serializers.Serializer):
    """Группа чатов доктора — один пациент и все его опекуны."""

    patient = ChatGroupMemberSerializer()
    caregivers = ChatGroupMemberSerializer(many=True)


class CaregiverChatGroupSerializer(serializers.Serializer):
    """Группа чатов опекуна — один пациент, его доктора и другие опекуны."""

    patient = ChatGroupMemberSerializer()
    doctors = ChatGroupMemberSerializer(many=True)
    caregivers = ChatGroupMemberSerializer(many=True)


class MessageSenderSerializer(serializers.Serializer):
    """Краткие данные отправителя сообщения."""

    id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()


class MessageSerializer(serializers.ModelSerializer):
    """Сообщение чата с данными отправителя."""

    sender = MessageSenderSerializer(read_only=True)
    content = serializers.SerializerMethodField()
    edited = serializers.BooleanField(source="is_edited", read_only=True)

    class Meta:
        """Метаданные сериализатора сообщения."""

        model = Message
        fields: ClassVar = ["id", "sender", "content", "is_deleted", "edited", "created_at"]

    def get_content(self, obj: Message) -> str | None:
        """Скрывает текст удалённого сообщения."""
        return None if obj.is_deleted else obj.content


class MessagePageSerializer(serializers.Serializer):
    """Страница сообщений с флагом наличия более старых записей."""

    results = MessageSerializer(many=True)
    has_more = serializers.BooleanField()
