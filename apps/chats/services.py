"""Сервисные функции для создания и поиска чатов."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Count

from apps.chats.models import Chat

if TYPE_CHECKING:
    from apps.users.models import User


def get_or_create_direct_chat(user_a: User, user_b: User) -> tuple[Chat, bool]:
    """Находит или создаёт приватный чат между двумя пользователями без дубликатов.

    Поиск ведётся по точному совпадению состава участников (ровно 2 человека).
    """
    # id__in вместо filter(participants=) — иначе ORM переиспользует JOIN для Count
    ids_with_a = Chat.objects.filter(participants=user_a).values("id")
    ids_with_b = Chat.objects.filter(participants=user_b).values("id")
    existing = (
        Chat.objects.filter(id__in=ids_with_a)
        .filter(id__in=ids_with_b)
        .annotate(participant_count=Count("participants", distinct=True))
        .filter(participant_count=2)
        .first()
    )
    if existing:
        return existing, False

    chat = Chat.objects.create()
    chat.participants.add(user_a, user_b)
    return chat, True
