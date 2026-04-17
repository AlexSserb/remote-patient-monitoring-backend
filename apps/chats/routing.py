"""WebSocket URL-маршруты приложения чатов."""

from __future__ import annotations

from django.urls import path

from apps.chats.consumers import ChatConsumer

websocket_urlpatterns = [
    path("ws/chats/<int:chat_id>/", ChatConsumer.as_asgi()),
]
