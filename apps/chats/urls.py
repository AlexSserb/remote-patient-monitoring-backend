"""URL-маршруты приложения чатов."""

from __future__ import annotations

from django.urls import path

from apps.chats.views import list_chat_groups, list_chats

urlpatterns = [
    path("", list_chats, name="chats-list"),
    path("groups/", list_chat_groups, name="chats-groups"),
]
