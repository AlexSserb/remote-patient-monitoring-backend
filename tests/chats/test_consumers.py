"""Тесты WebSocket-консьюмера чата: подключение, отправка, удаление и редактирование сообщений."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
from channels import DEFAULT_CHANNEL_LAYER
from channels.layers import channel_layers
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser
from django.urls import path

from apps.chats.consumers import ChatConsumer
from apps.chats.models import Chat, Message
from apps.users.models import User

pytestmark = pytest.mark.django_db(transaction=True)


def _make_ws_app(user: User) -> Any:
    """Создаёт тестовое ASGI-приложение с внедрённым пользователем в scope (обход JWT middleware)."""

    class _InjectUser:
        def __init__(self, inner: Any) -> None:
            self.inner = inner

        async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
            scope["user"] = user
            await self.inner(scope, receive, send)

    return _InjectUser(URLRouter([path("ws/chats/<int:chat_id>/", ChatConsumer.as_asgi())]))


@pytest.fixture(autouse=True)
def in_memory_channel_layer(settings: Any) -> Generator[None, None, None]:
    """Заменяет Redis channel layer на in-memory для изоляции тестов от внешних зависимостей."""
    settings.CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
    # Сбрасываем кэш, чтобы следующий доступ создал новый экземпляр с обновлёнными настройками
    channel_layers.backends.pop(DEFAULT_CHANNEL_LAYER, None)
    yield
    channel_layers.backends.pop(DEFAULT_CHANNEL_LAYER, None)


# ---------------------------------------------------------------------------
# Подключение
# ---------------------------------------------------------------------------


class TestChatConsumerConnect:
    """Тесты авторизации и подключения WebSocket-соединения."""

    async def test_participant_connects_successfully(
        self, doctor: User, patient: User, doctor_patient_link: None
    ) -> None:
        """Участник чата успешно устанавливает WebSocket-соединение."""
        chat = await Chat.objects.filter(participants=doctor).afirst()
        assert chat is not None
        communicator = WebsocketCommunicator(_make_ws_app(doctor), f"/ws/chats/{chat.pk}/")
        connected, _ = await communicator.connect()
        assert connected
        await communicator.disconnect()

    async def test_unauthenticated_closes_with_4001(
        self, doctor: User, patient: User, doctor_patient_link: None
    ) -> None:
        """Неаутентифицированный пользователь получает код закрытия 4001."""
        chat = await Chat.objects.filter(participants=doctor).afirst()
        assert chat is not None

        class _AnonApp:
            def __init__(self, inner: Any) -> None:
                self.inner = inner

            async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
                scope["user"] = AnonymousUser()
                await self.inner(scope, receive, send)

        app = _AnonApp(URLRouter([path("ws/chats/<int:chat_id>/", ChatConsumer.as_asgi())]))
        communicator = WebsocketCommunicator(app, f"/ws/chats/{chat.pk}/")
        connected, code = await communicator.connect()
        assert not connected
        assert code == 4001

    async def test_non_participant_closes_with_4003(
        self, doctor: User, patient: User, caregiver: User, doctor_patient_link: None
    ) -> None:
        """Пользователь, не являющийся участником чата, получает код закрытия 4003."""
        chat = await Chat.objects.filter(participants=doctor).afirst()
        assert chat is not None
        communicator = WebsocketCommunicator(_make_ws_app(caregiver), f"/ws/chats/{chat.pk}/")
        connected, code = await communicator.connect()
        assert not connected
        assert code == 4003


# ---------------------------------------------------------------------------
# Отправка сообщений
# ---------------------------------------------------------------------------


class TestChatConsumerSendMessage:
    """Тесты отправки новых сообщений через WebSocket."""

    @pytest.fixture
    async def connected(
        self, doctor: User, patient: User, doctor_patient_link: None
    ) -> AsyncGenerator[tuple[WebsocketCommunicator, Chat], None]:
        """Открытый WebsocketCommunicator от имени доктора с объектом чата."""
        chat = await Chat.objects.filter(participants=doctor).afirst()
        assert chat is not None
        communicator = WebsocketCommunicator(_make_ws_app(doctor), f"/ws/chats/{chat.pk}/")
        await communicator.connect()
        yield communicator, chat
        await communicator.disconnect()

    async def test_send_valid_message_broadcasts_and_persists(
        self, connected: tuple[WebsocketCommunicator, Chat]
    ) -> None:
        """Корректное сообщение сохраняется в БД и рассылается участникам чата."""
        communicator, chat = connected
        await communicator.send_json_to({"type": "message", "content": "Привет"})
        data = await communicator.receive_json_from()
        assert data["type"] == "chat.message"
        assert data["message"]["content"] == "Привет"
        assert await Message.objects.filter(chat=chat, content="Привет").aexists()

    async def test_send_empty_content_returns_error(self, connected: tuple[WebsocketCommunicator, Chat]) -> None:
        """Пустое (или состоящее только из пробелов) сообщение отклоняется с кодом empty_content."""
        communicator, _ = connected
        await communicator.send_json_to({"type": "message", "content": "   "})
        data = await communicator.receive_json_from()
        assert data["type"] == "error"
        assert data["code"] == "empty_content"

    async def test_send_too_long_content_returns_error(self, connected: tuple[WebsocketCommunicator, Chat]) -> None:
        """Сообщение длиннее 10 000 символов отклоняется с кодом too_long."""
        communicator, _ = connected
        await communicator.send_json_to({"type": "message", "content": "x" * 10_001})
        data = await communicator.receive_json_from()
        assert data["type"] == "error"
        assert data["code"] == "too_long"

    async def test_send_message_updates_last_message_at(self, connected: tuple[WebsocketCommunicator, Chat]) -> None:
        """Отправка первого сообщения выставляет last_message_at у чата."""
        communicator, chat = connected
        assert chat.last_message_at is None
        await communicator.send_json_to({"type": "message", "content": "Тест"})
        await communicator.receive_json_from()
        updated = await Chat.objects.aget(pk=chat.pk)
        assert updated.last_message_at is not None

    async def test_send_invalid_json_returns_error(self, connected: tuple[WebsocketCommunicator, Chat]) -> None:
        """Некорректный JSON отклоняется с кодом invalid_json."""
        communicator, _ = connected
        await communicator.send_to(text_data="not json {{{")
        data = await communicator.receive_json_from()
        assert data["type"] == "error"
        assert data["code"] == "invalid_json"


# ---------------------------------------------------------------------------
# Удаление сообщений
# ---------------------------------------------------------------------------


class TestChatConsumerDeleteMessage:
    """Тесты удаления сообщений через WebSocket."""

    @pytest.fixture
    async def connected_with_message(
        self, doctor: User, patient: User, doctor_patient_link: None
    ) -> AsyncGenerator[tuple[WebsocketCommunicator, int], None]:
        """Открытый коммуникатор от имени доктора и id отправленного им сообщения."""
        chat = await Chat.objects.filter(participants=doctor).afirst()
        assert chat is not None
        communicator = WebsocketCommunicator(_make_ws_app(doctor), f"/ws/chats/{chat.pk}/")
        await communicator.connect()
        await communicator.send_json_to({"type": "message", "content": "Сообщение для удаления"})
        response = await communicator.receive_json_from()
        message_id: int = response["message"]["id"]
        yield communicator, message_id
        await communicator.disconnect()

    async def test_delete_own_message_broadcasts_and_soft_deletes(
        self, connected_with_message: tuple[WebsocketCommunicator, int]
    ) -> None:
        """Автор сообщения удаляет его: получает событие chat.message_deleted, is_deleted=True в БД."""
        communicator, message_id = connected_with_message
        await communicator.send_json_to({"type": "delete", "message_id": message_id})
        data = await communicator.receive_json_from()
        assert data["type"] == "chat.message_deleted"
        assert data["message_id"] == message_id
        msg = await Message.objects.aget(pk=message_id)
        assert msg.is_deleted is True

    async def test_delete_nonexistent_message_returns_error(
        self, connected_with_message: tuple[WebsocketCommunicator, int]
    ) -> None:
        """Попытка удалить несуществующий message_id возвращает ошибку not_found."""
        communicator, _ = connected_with_message
        await communicator.send_json_to({"type": "delete", "message_id": 999_999})
        data = await communicator.receive_json_from()
        assert data["type"] == "error"
        assert data["code"] == "not_found"

    async def test_delete_other_users_message_returns_error(
        self, doctor: User, patient: User, doctor_patient_link: None
    ) -> None:
        """Попытка удалить сообщение другого участника возвращает ошибку not_found."""
        chat = await Chat.objects.filter(participants=doctor).afirst()
        assert chat is not None

        # Пациент отправляет сообщение и сразу отключается
        patient_comm = WebsocketCommunicator(_make_ws_app(patient), f"/ws/chats/{chat.pk}/")
        await patient_comm.connect()
        await patient_comm.send_json_to({"type": "message", "content": "Сообщение пациента"})
        patient_response = await patient_comm.receive_json_from()
        message_id: int = patient_response["message"]["id"]
        await patient_comm.disconnect()

        # Доктор пытается удалить сообщение пациента
        doctor_comm = WebsocketCommunicator(_make_ws_app(doctor), f"/ws/chats/{chat.pk}/")
        await doctor_comm.connect()
        await doctor_comm.send_json_to({"type": "delete", "message_id": message_id})
        data = await doctor_comm.receive_json_from()
        await doctor_comm.disconnect()

        assert data["type"] == "error"
        assert data["code"] == "not_found"

    async def test_delete_with_non_integer_id_returns_error(
        self, connected_with_message: tuple[WebsocketCommunicator, int]
    ) -> None:
        """Передача message_id не целого типа возвращает ошибку invalid_message_id."""
        communicator, _ = connected_with_message
        await communicator.send_json_to({"type": "delete", "message_id": "abc"})
        data = await communicator.receive_json_from()
        assert data["type"] == "error"
        assert data["code"] == "invalid_message_id"


# ---------------------------------------------------------------------------
# Редактирование сообщений
# ---------------------------------------------------------------------------


class TestChatConsumerEditMessage:
    """Тесты редактирования сообщений через WebSocket."""

    @pytest.fixture
    async def connected_with_message(
        self, doctor: User, patient: User, doctor_patient_link: None
    ) -> AsyncGenerator[tuple[WebsocketCommunicator, int], None]:
        """Открытый коммуникатор от имени доктора и id отправленного им сообщения."""
        chat = await Chat.objects.filter(participants=doctor).afirst()
        assert chat is not None
        communicator = WebsocketCommunicator(_make_ws_app(doctor), f"/ws/chats/{chat.pk}/")
        await communicator.connect()
        await communicator.send_json_to({"type": "message", "content": "Оригинальный текст"})
        response = await communicator.receive_json_from()
        message_id: int = response["message"]["id"]
        yield communicator, message_id
        await communicator.disconnect()

    async def test_edit_own_message_broadcasts_and_persists(
        self, connected_with_message: tuple[WebsocketCommunicator, int]
    ) -> None:
        """Автор сообщения редактирует его: получает событие chat.message_edited, данные обновлены в БД."""
        communicator, message_id = connected_with_message
        await communicator.send_json_to({"type": "edit", "message_id": message_id, "content": "Изменённый текст"})
        data = await communicator.receive_json_from()
        assert data["type"] == "chat.message_edited"
        assert data["message_id"] == message_id
        assert data["content"] == "Изменённый текст"
        msg = await Message.objects.aget(pk=message_id)
        assert msg.content == "Изменённый текст"
        assert msg.is_edited is True

    async def test_edit_empty_content_returns_error(
        self, connected_with_message: tuple[WebsocketCommunicator, int]
    ) -> None:
        """Редактирование с пустым контентом возвращает ошибку empty_content."""
        communicator, message_id = connected_with_message
        await communicator.send_json_to({"type": "edit", "message_id": message_id, "content": "   "})
        data = await communicator.receive_json_from()
        assert data["type"] == "error"
        assert data["code"] == "empty_content"

    async def test_edit_too_long_content_returns_error(
        self, connected_with_message: tuple[WebsocketCommunicator, int]
    ) -> None:
        """Редактирование сообщением длиннее 10 000 символов возвращает ошибку too_long."""
        communicator, message_id = connected_with_message
        await communicator.send_json_to({"type": "edit", "message_id": message_id, "content": "x" * 10_001})
        data = await communicator.receive_json_from()
        assert data["type"] == "error"
        assert data["code"] == "too_long"

    async def test_edit_nonexistent_message_returns_error(
        self, connected_with_message: tuple[WebsocketCommunicator, int]
    ) -> None:
        """Попытка редактировать несуществующий message_id возвращает ошибку not_found."""
        communicator, _ = connected_with_message
        await communicator.send_json_to({"type": "edit", "message_id": 999_999, "content": "Текст"})
        data = await communicator.receive_json_from()
        assert data["type"] == "error"
        assert data["code"] == "not_found"

    async def test_edit_other_users_message_returns_error(
        self, doctor: User, patient: User, doctor_patient_link: None
    ) -> None:
        """Попытка редактировать сообщение другого участника возвращает ошибку not_found."""
        chat = await Chat.objects.filter(participants=doctor).afirst()
        assert chat is not None

        # Пациент отправляет сообщение и сразу отключается
        patient_comm = WebsocketCommunicator(_make_ws_app(patient), f"/ws/chats/{chat.pk}/")
        await patient_comm.connect()
        await patient_comm.send_json_to({"type": "message", "content": "Сообщение пациента"})
        patient_response = await patient_comm.receive_json_from()
        message_id: int = patient_response["message"]["id"]
        await patient_comm.disconnect()

        # Доктор пытается редактировать сообщение пациента
        doctor_comm = WebsocketCommunicator(_make_ws_app(doctor), f"/ws/chats/{chat.pk}/")
        await doctor_comm.connect()
        await doctor_comm.send_json_to({"type": "edit", "message_id": message_id, "content": "Попытка"})
        data = await doctor_comm.receive_json_from()
        await doctor_comm.disconnect()

        assert data["type"] == "error"
        assert data["code"] == "not_found"

    async def test_edit_deleted_message_returns_error(
        self, connected_with_message: tuple[WebsocketCommunicator, int]
    ) -> None:
        """Попытка редактировать мягко удалённое сообщение возвращает ошибку not_found."""
        communicator, message_id = connected_with_message

        # Сначала удаляем сообщение
        await communicator.send_json_to({"type": "delete", "message_id": message_id})
        await communicator.receive_json_from()

        # Затем пытаемся его редактировать
        await communicator.send_json_to({"type": "edit", "message_id": message_id, "content": "Текст после удаления"})
        data = await communicator.receive_json_from()
        assert data["type"] == "error"
        assert data["code"] == "not_found"

    async def test_edit_with_non_integer_id_returns_error(
        self, connected_with_message: tuple[WebsocketCommunicator, int]
    ) -> None:
        """Передача message_id не целого типа при редактировании возвращает ошибку invalid_message_id."""
        communicator, _ = connected_with_message
        await communicator.send_json_to({"type": "edit", "message_id": "not_an_int", "content": "Текст"})
        data = await communicator.receive_json_from()
        assert data["type"] == "error"
        assert data["code"] == "invalid_message_id"
