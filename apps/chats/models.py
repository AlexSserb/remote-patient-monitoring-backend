"""Модели чатов системы мониторинга."""

from __future__ import annotations

from typing import ClassVar

from django.conf import settings
from django.db import models


class Chat(models.Model):
    """Чат между двумя или более участниками системы."""

    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="chats",
        verbose_name="Участники",
    )
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="patient_chats",
        null=True,
        blank=True,
        verbose_name="Пациент",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    last_message_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата последнего сообщения",
    )

    class Meta:
        """Метаданные модели чата."""

        verbose_name = "Чат"
        verbose_name_plural = "Чаты"
        ordering: ClassVar = ["-last_message_at", "-created_at"]

    def __str__(self) -> str:
        """Возвращает строковое представление чата через перечисление участников."""
        ids = list(self.participants.values_list("id", flat=True))
        return f"Chat(participants={ids})"


class Message(models.Model):
    """Сообщение в чате между участниками системы мониторинга."""

    chat = models.ForeignKey(
        Chat,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name="Чат",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
        verbose_name="Отправитель",
    )
    content = models.TextField(verbose_name="Текст сообщения")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата отправки")

    class Meta:
        """Метаданные модели сообщения."""

        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"
        # убывающий порядок по id — самые новые первыми, id монотонен и индексирован
        ordering: ClassVar = ["-id"]
        indexes: ClassVar = [
            models.Index(fields=["chat", "-id"], name="message_chat_id_idx"),
        ]

    def __str__(self) -> str:
        """Возвращает краткое строковое представление сообщения."""
        return f"Message(chat={self.chat_id}, sender={self.sender_id}, id={self.pk})"  # ty: ignore[unresolved-attribute]
