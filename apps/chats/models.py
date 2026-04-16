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
