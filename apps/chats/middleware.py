"""ASGI-middleware для аутентификации WebSocket-соединений через JWT из query string."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

if TYPE_CHECKING:
    from django.contrib.auth.base_user import AbstractBaseUser


@database_sync_to_async
def _get_user_from_token(raw_token: str) -> AbstractBaseUser | AnonymousUser:
    """Валидирует JWT и возвращает пользователя или AnonymousUser при ошибке."""
    user_model = get_user_model()
    try:
        token = AccessToken(raw_token)  # ty: ignore[invalid-argument-type]
        return user_model.objects.get(pk=token["user_id"])
    except InvalidToken, TokenError, user_model.DoesNotExist:
        return AnonymousUser()


class JwtAuthMiddleware:
    """Middleware, добавляющий пользователя в scope WS-соединения по токену из query string."""

    def __init__(self, inner: Any) -> None:
        """Инициализирует middleware с вложенным ASGI-приложением."""
        self.inner = inner

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        """Извлекает токен из ?token=, аутентифицирует и передаёт управление дальше."""
        if scope["type"] == "websocket":
            qs = parse_qs(scope.get("query_string", b"").decode())
            token_list = qs.get("token", [])
            raw_token = token_list[0] if token_list else ""
            scope["user"] = await _get_user_from_token(raw_token)

        await self.inner(scope, receive, send)
