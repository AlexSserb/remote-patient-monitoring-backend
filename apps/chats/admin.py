"""Регистрация моделей чатов в административной панели."""

from __future__ import annotations

from typing import ClassVar

from django.contrib import admin

from apps.chats.models import Chat


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    """Отображение чатов в админке с фильтрацией по дате последнего сообщения."""

    list_display: ClassVar = ["id", "created_at", "last_message_at"]
    list_filter: ClassVar = ["last_message_at"]
    filter_horizontal: ClassVar = ["participants"]
