"""Тесты сервисных функций создания и поиска чатов, отправки и редактирования сообщений."""

from __future__ import annotations

import pytest

from apps.chats.models import Chat, Message
from apps.chats.services import edit_message, get_or_create_direct_chat, send_message
from apps.users.models import User

pytestmark = pytest.mark.django_db


class TestGetOrCreateDirectChat:
    """Тесты функции get_or_create_direct_chat."""

    def test_creates_new_chat(self, doctor: User, patient: User) -> None:
        """Создаёт новый чат между двумя пользователями, которые раньше не общались."""
        chat, created = get_or_create_direct_chat(doctor, patient, patient)
        assert created is True
        assert chat.pk is not None
        assert chat.participants.count() == 2

    def test_returns_existing_chat(self, doctor: User, patient: User) -> None:
        """Возвращает существующий чат при повторном вызове без создания дубликата."""
        chat1, _ = get_or_create_direct_chat(doctor, patient, patient)
        chat2, created = get_or_create_direct_chat(doctor, patient, patient)
        assert created is False
        assert chat1.pk == chat2.pk
        assert Chat.objects.count() == 1

    def test_symmetric_lookup(self, doctor: User, patient: User) -> None:
        """Находит один и тот же чат независимо от порядка передачи участников."""
        chat1, _ = get_or_create_direct_chat(doctor, patient, patient)
        chat2, created = get_or_create_direct_chat(patient, doctor, patient)
        assert created is False
        assert chat1.pk == chat2.pk

    def test_different_pairs_create_different_chats(self, doctor: User, patient: User, caregiver: User) -> None:
        """Создаёт отдельные чаты для разных пар пользователей в контексте одного пациента."""
        chat_dp, _ = get_or_create_direct_chat(doctor, patient, patient)
        chat_dc, _ = get_or_create_direct_chat(doctor, caregiver, patient)
        assert chat_dp.pk != chat_dc.pk
        assert Chat.objects.count() == 2

    def test_chat_has_no_last_message_at_by_default(self, doctor: User, patient: User) -> None:
        """Новый чат создаётся без даты последнего сообщения."""
        chat, _ = get_or_create_direct_chat(doctor, patient, patient)
        assert chat.last_message_at is None


# ---------------------------------------------------------------------------
# send_message
# ---------------------------------------------------------------------------


class TestSendMessage:
    """Тесты функции send_message."""

    def test_creates_message_with_correct_fields(self, doctor: User, patient: User, doctor_patient_link: None) -> None:
        """Создаёт сообщение с правильными значениями chat, sender и content."""
        chat = Chat.objects.filter(participants=doctor).first()
        assert chat is not None
        message = send_message(chat, doctor, "Тест")
        assert message.pk is not None
        assert message.chat == chat
        assert message.sender == doctor
        assert message.content == "Тест"
        assert message.is_deleted is False
        assert message.is_edited is False

    def test_updates_last_message_at(self, doctor: User, patient: User, doctor_patient_link: None) -> None:
        """Обновляет last_message_at чата после отправки первого сообщения."""
        chat = Chat.objects.filter(participants=doctor).first()
        assert chat is not None
        assert chat.last_message_at is None
        send_message(chat, doctor, "Тест")
        chat.refresh_from_db()
        assert chat.last_message_at is not None

    def test_returns_message_instance(self, doctor: User, patient: User, doctor_patient_link: None) -> None:
        """Возвращает объект Message, а не None или другой тип."""
        chat = Chat.objects.filter(participants=doctor).first()
        assert chat is not None
        result = send_message(chat, doctor, "Тест")
        assert isinstance(result, Message)


# ---------------------------------------------------------------------------
# edit_message
# ---------------------------------------------------------------------------


class TestEditMessage:
    """Тесты функции edit_message."""

    @pytest.fixture
    def chat_and_message(self, doctor: User, patient: User, doctor_patient_link: None) -> tuple[Chat, Message]:
        """Возвращает чат доктора с пациентом и исходное сообщение от доктора."""
        chat = Chat.objects.filter(participants=doctor).first()
        assert chat is not None
        message = send_message(chat, doctor, "Оригинал")
        return chat, message

    def test_updates_content_and_sets_flag(self, doctor: User, chat_and_message: tuple[Chat, Message]) -> None:
        """Обновляет текст сообщения и выставляет флаг is_edited=True, возвращает True."""
        chat, message = chat_and_message
        result = edit_message(message.pk, chat, doctor.pk, "Новый текст")
        assert result is True
        message.refresh_from_db()
        assert message.content == "Новый текст"
        assert message.is_edited is True

    def test_returns_false_for_wrong_sender(self, patient: User, chat_and_message: tuple[Chat, Message]) -> None:
        """Возвращает False и не меняет сообщение при попытке редактирования чужого сообщения."""
        chat, message = chat_and_message
        result = edit_message(message.pk, chat, patient.pk, "Попытка")
        assert result is False
        message.refresh_from_db()
        assert message.content == "Оригинал"

    def test_returns_false_for_wrong_chat(
        self,
        doctor: User,
        caregiver: User,
        caregiver_patient_link: None,
        chat_and_message: tuple[Chat, Message],
    ) -> None:
        """Возвращает False при передаче чата, которому сообщение не принадлежит."""
        _, message = chat_and_message
        other_chat = Chat.objects.filter(participants=caregiver).first()
        assert other_chat is not None
        result = edit_message(message.pk, other_chat, doctor.pk, "Попытка")
        assert result is False

    def test_returns_false_for_deleted_message(self, doctor: User, chat_and_message: tuple[Chat, Message]) -> None:
        """Возвращает False при попытке редактирования мягко удалённого сообщения."""
        chat, message = chat_and_message
        message.is_deleted = True
        message.save(update_fields=["is_deleted"])
        result = edit_message(message.pk, chat, doctor.pk, "Попытка")
        assert result is False

    def test_returns_false_for_nonexistent_message(self, doctor: User, chat_and_message: tuple[Chat, Message]) -> None:
        """Возвращает False при указании несуществующего message_id."""
        chat, _ = chat_and_message
        result = edit_message(999_999, chat, doctor.pk, "Попытка")
        assert result is False
