"""Тесты сервисной функции создания и поиска чатов."""

from __future__ import annotations

import pytest

from apps.chats.models import Chat
from apps.chats.services import get_or_create_direct_chat
from apps.users.models import User

pytestmark = pytest.mark.django_db


class TestGetOrCreateDirectChat:
    """Тесты функции get_or_create_direct_chat."""

    def test_creates_new_chat(self, doctor: User, patient: User) -> None:
        """Создаёт новый чат между двумя пользователями, которые раньше не общались."""
        chat, created = get_or_create_direct_chat(doctor, patient)
        assert created is True
        assert chat.pk is not None
        assert chat.participants.count() == 2

    def test_returns_existing_chat(self, doctor: User, patient: User) -> None:
        """Возвращает существующий чат при повторном вызове без создания дубликата."""
        chat1, _ = get_or_create_direct_chat(doctor, patient)
        chat2, created = get_or_create_direct_chat(doctor, patient)
        assert created is False
        assert chat1.pk == chat2.pk
        assert Chat.objects.count() == 1

    def test_symmetric_lookup(self, doctor: User, patient: User) -> None:
        """Находит один и тот же чат независимо от порядка передачи участников."""
        chat1, _ = get_or_create_direct_chat(doctor, patient)
        chat2, created = get_or_create_direct_chat(patient, doctor)
        assert created is False
        assert chat1.pk == chat2.pk

    def test_different_pairs_create_different_chats(self, doctor: User, patient: User, caregiver: User) -> None:
        """Создаёт отдельные чаты для разных пар пользователей."""
        chat_dp, _ = get_or_create_direct_chat(doctor, patient)
        chat_dc, _ = get_or_create_direct_chat(doctor, caregiver)
        assert chat_dp.pk != chat_dc.pk
        assert Chat.objects.count() == 2

    def test_chat_has_no_last_message_at_by_default(self, doctor: User, patient: User) -> None:
        """Новый чат создаётся без даты последнего сообщения."""
        chat, _ = get_or_create_direct_chat(doctor, patient)
        assert chat.last_message_at is None
