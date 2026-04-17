"""Сервисные функции для создания, поиска чатов и отправки сообщений."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Count
from django.utils import timezone

from apps.chats.models import Chat, Message

if TYPE_CHECKING:
    from apps.users.models import User


def get_or_create_direct_chat(user_a: User, user_b: User, patient: User) -> tuple[Chat, bool]:
    """Находит или создаёт приватный чат между двумя пользователями в контексте пациента.

    Поиск ведётся по точному совпадению участников (ровно 2) и пациента,
    чтобы один и тот же врач/опекун имел отдельный чат для каждого пациента.
    """
    # id__in вместо filter(participants=) — иначе ORM переиспользует JOIN для Count
    ids_with_a = Chat.objects.filter(participants=user_a).values("id")
    ids_with_b = Chat.objects.filter(participants=user_b).values("id")
    existing = (
        Chat.objects.filter(id__in=ids_with_a)
        .filter(id__in=ids_with_b)
        .filter(patient=patient)
        .annotate(participant_count=Count("participants", distinct=True))
        .filter(participant_count=2)
        .first()
    )
    if existing:
        return existing, False

    chat = Chat.objects.create(patient=patient)
    chat.participants.add(user_a, user_b)
    return chat, True


MESSAGE_PAGE_SIZE = 100


def send_message(chat: Chat, sender: User, content: str) -> Message:
    """Создаёт сообщение и атомарно обновляет время последнего сообщения в чате."""
    message = Message.objects.create(chat=chat, sender=sender, content=content)
    # update() — один запрос без гонки условий, не трогает другие поля чата
    Chat.objects.filter(pk=chat.pk).update(last_message_at=timezone.now())
    return message


def get_messages_page(chat: Chat, before_id: int | None) -> tuple[list[Message], bool]:
    """Возвращает страницу сообщений и флаг наличия более старых записей.

    Загружает MESSAGE_PAGE_SIZE + 1 запись для проверки наличия следующей страницы
    без дополнительного COUNT-запроса.
    """
    qs = Message.objects.filter(chat=chat).select_related("sender")
    if before_id is not None:
        qs = qs.filter(id__lt=before_id)

    # запрашиваем на одну запись больше, чтобы понять, есть ли ещё страницы
    rows = list(qs[: MESSAGE_PAGE_SIZE + 1])
    has_more = len(rows) > MESSAGE_PAGE_SIZE
    return rows[:MESSAGE_PAGE_SIZE], has_more
