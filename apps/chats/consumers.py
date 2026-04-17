"""WebSocket-консьюмер для обмена сообщениями в чате в реальном времени."""

from __future__ import annotations

import json
import logging
from typing import Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from apps.chats.models import Chat
from apps.chats.serializers import MessageSerializer
from apps.chats.services import send_message

logger = logging.getLogger(__name__)


def _channel_group_name(chat_id: int | str) -> str:
    """Возвращает имя группы канала для чата по его id."""
    return f"chat_{chat_id}"


@database_sync_to_async
def _get_chat_if_participant(chat_id: int, user_id: int) -> Chat | None:
    """Возвращает чат, если пользователь является его участником, иначе None."""
    try:
        chat = Chat.objects.get(pk=chat_id)
    except Chat.DoesNotExist:
        return None
    if not chat.participants.filter(pk=user_id).exists():
        return None
    return chat


@database_sync_to_async
def _create_message(chat: Chat, user: Any, content: str) -> dict:
    """Создаёт сообщение и возвращает его сериализованное представление."""
    message = send_message(chat, user, content)
    # select_related необходим — sender уже загружен через send_message, но сериализатор
    # обращается к полям sender, поэтому обновляем объект с нужными данными
    message.sender = user
    return MessageSerializer(message).data


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket-консьюмер чата: подключение, получение и рассылка сообщений."""

    async def connect(self) -> None:
        """Проверяет аутентификацию и членство в чате, добавляет в группу канала."""
        user = self.scope.get("user")
        if not user or isinstance(user, AnonymousUser):
            await self.close(code=4001)
            return

        chat_id: int = self.scope["url_route"]["kwargs"]["chat_id"]
        chat = await _get_chat_if_participant(chat_id, user.pk)
        if chat is None:
            await self.close(code=4003)
            return

        self.chat = chat
        self.group_name = _channel_group_name(chat_id)

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.debug("WS connected: user=%d chat=%d", user.pk, chat_id)

    async def disconnect(self, code: int) -> None:
        """Удаляет соединение из группы канала при отключении."""
        group_name = getattr(self, "group_name", None)
        if group_name:
            await self.channel_layer.group_discard(group_name, self.channel_name)
            logger.debug("WS disconnected: code=%d channel=%s", code, self.channel_name)

    async def receive(self, text_data: str | None = None, bytes_data: bytes | None = None) -> None:  # noqa: ARG002
        """Принимает сообщение от клиента, сохраняет и рассылает всем участникам чата."""
        if not text_data:
            return

        try:
            payload = json.loads(text_data)
            content: str = payload.get("content", "").strip()
        except json.JSONDecodeError, AttributeError:
            await self._send_error("invalid_json", "Некорректный формат сообщения.")
            return

        if not content:
            await self._send_error("empty_content", "Сообщение не может быть пустым.")
            return

        if len(content) > 10_000:  # noqa: PLR2004
            await self._send_error("too_long", "Сообщение превышает допустимую длину.")
            return

        user = self.scope["user"]
        message_data = await _create_message(self.chat, user, content)

        # Рассылаем сообщение всем участникам группы (включая отправителя)
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "chat.message", "message": message_data},
        )

    async def chat_message(self, event: dict) -> None:
        """Обработчик группового события — доставляет сообщение клиенту через WS."""
        await self.send(text_data=json.dumps({"type": "chat.message", "message": event["message"]}))

    async def _send_error(self, code: str, detail: str) -> None:
        """Отправляет клиенту сообщение об ошибке без закрытия соединения."""
        await self.send(text_data=json.dumps({"type": "error", "code": code, "detail": detail}))
