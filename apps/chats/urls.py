"""URL-маршруты приложения чатов."""

from __future__ import annotations

from django.urls import path

from apps.chats.views import (
    delete_message,
    list_caregiver_chat_groups,
    list_chats,
    list_doctor_chat_groups,
    list_messages,
)

urlpatterns = [
    path("", list_chats, name="chats-list"),
    path("doctor-groups/", list_doctor_chat_groups, name="chats-doctor-groups"),
    path("caregiver-groups/", list_caregiver_chat_groups, name="chats-caregiver-groups"),
    path("<int:chat_id>/messages/", list_messages, name="chat-messages-list"),
    path("<int:chat_id>/messages/<int:message_id>/", delete_message, name="chat-message-delete"),
]
