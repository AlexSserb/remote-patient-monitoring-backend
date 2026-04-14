"""Сервисный слой: OTP, подписанные токены первого шага, JWT-блэклист, email."""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime
from typing import Any

import redis
from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

logger = logging.getLogger(__name__)

# Соль для подписи pre_auth_token (уникальна для данного назначения)
_PRE_AUTH_SALT = "pre_auth_v1"
# Время жизни pre_auth_token и OTP в секундах
_PRE_AUTH_MAX_AGE = 300
_OTP_TTL = 300


def _get_redis() -> redis.Redis[str]:
    """Возвращает клиент Redis с декодированием ответов в строки."""
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


def generate_and_store_otp(user_id: int) -> str:
    """Генерирует криптографически стойкий 6-значный OTP и сохраняет его в Redis."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    _get_redis().setex(f"otp:{user_id}", _OTP_TTL, code)
    return code


def verify_and_consume_otp(user_id: int, code: str) -> bool:
    """Проверяет OTP по значению в Redis и удаляет его при успехе (одноразовое использование)."""
    client = _get_redis()
    key = f"otp:{user_id}"
    stored = client.get(key)
    # secrets.compare_digest защищает от timing-атак при сравнении кодов
    if stored is not None and secrets.compare_digest(stored, code):
        client.delete(key)
        return True
    return False


def create_pre_auth_token(user_id: int) -> str:
    """Создаёт подписанный Django-signing токен первого шага аутентификации."""
    return signing.dumps({"uid": user_id}, salt=_PRE_AUTH_SALT)


def decode_pre_auth_token(token: str) -> int:
    """Декодирует и верифицирует pre_auth_token, возвращает user_id или бросает ValueError."""
    try:
        data: dict[str, Any] = signing.loads(
            token,
            salt=_PRE_AUTH_SALT,
            max_age=_PRE_AUTH_MAX_AGE,
        )
    except signing.SignatureExpired as exc:
        msg = "Pre-auth token has expired"
        raise ValueError(msg) from exc
    except signing.BadSignature as exc:
        msg = "Pre-auth token is invalid"
        raise ValueError(msg) from exc
    return int(data["uid"])


def blacklist_refresh_token(raw_refresh: str) -> None:
    """Добавляет JTI refresh-токена в Redis-блэклист с TTL равным оставшемуся времени жизни."""
    try:
        token = RefreshToken(raw_refresh)
    except TokenError as exc:
        msg = "Invalid refresh token"
        raise ValueError(msg) from exc

    jti: str = token[jwt_settings.JTI_CLAIM]
    exp: int = token["exp"]
    # Рассчитываем оставшееся время жизни, чтобы Redis автоматически удалил запись
    ttl = max(0, exp - int(datetime.now(tz=UTC).timestamp()))
    if ttl > 0:
        _get_redis().setex(f"blacklist:jti:{jti}", ttl, "1")


def is_refresh_token_blacklisted(jti: str) -> bool:
    """Проверяет наличие JTI в Redis-блэклисте."""
    return _get_redis().exists(f"blacklist:jti:{jti}") > 0


def _build_token_pair(user_id: int) -> dict[str, str]:
    """Создаёт новую пару JWT-токенов с заданным user_id без обращения к базе данных."""
    refresh = RefreshToken()
    refresh[jwt_settings.USER_ID_CLAIM] = user_id
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def issue_token_pair(user: Any) -> dict[str, str]:
    """Выпускает пару JWT access/refresh для переданного объекта пользователя."""
    return _build_token_pair(user.pk)


def rotate_refresh_token(raw_refresh: str) -> dict[str, str]:
    """Ротирует refresh-токен: проверяет блэклист, инвалидирует старый, выпускает новую пару."""
    try:
        old_token = RefreshToken(raw_refresh)
    except TokenError as exc:
        msg = "Invalid refresh token"
        raise ValueError(msg) from exc

    jti: str = old_token[jwt_settings.JTI_CLAIM]

    if is_refresh_token_blacklisted(jti):
        msg = "Refresh token has been revoked"
        raise ValueError(msg)

    user_id: int = old_token[jwt_settings.USER_ID_CLAIM]

    # Инвалидируем старый токен до выпуска нового для предотвращения параллельного использования
    exp: int = old_token["exp"]
    ttl = max(0, exp - int(datetime.now(tz=UTC).timestamp()))
    if ttl > 0:
        _get_redis().setex(f"blacklist:jti:{jti}", ttl, "1")

    return _build_token_pair(user_id)


def send_otp_email(email: str, otp: str) -> None:
    """Отправляет одноразовый код подтверждения входа на указанный email."""
    send_mail(
        subject="Код подтверждения входа",
        message=f"Ваш код подтверждения: {otp}\n\nКод действителен 5 минут.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )
    logger.info("OTP email sent to %s", email)


# Время жизни OTP и ожидающего адреса при смене email
_EMAIL_CHANGE_TTL = 300


def generate_and_store_email_change_otp(user_id: int, new_email: str) -> str:
    """Генерирует OTP для смены email и сохраняет код и новый адрес в Redis."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    client = _get_redis()
    client.setex(f"email_change_otp:{user_id}", _EMAIL_CHANGE_TTL, code)
    client.setex(f"email_change_pending:{user_id}", _EMAIL_CHANGE_TTL, new_email)
    return code


def verify_and_consume_email_change_otp(user_id: int, code: str) -> str | None:
    """Проверяет OTP смены email и возвращает новый адрес при успехе, иначе None."""
    client = _get_redis()
    otp_key = f"email_change_otp:{user_id}"
    email_key = f"email_change_pending:{user_id}"
    stored_otp = client.get(otp_key)
    stored_email = client.get(email_key)
    if stored_otp is None or stored_email is None:
        return None
    # secrets.compare_digest защищает от timing-атак
    if not secrets.compare_digest(stored_otp, code):
        return None
    # Удаляем ключи одной командой — код одноразовый
    client.delete(otp_key, email_key)
    return stored_email


def send_email_change_otp(new_email: str, otp: str) -> None:
    """Отправляет код подтверждения смены email на новый адрес."""
    send_mail(
        subject="Подтверждение смены email",
        message=f"Ваш код подтверждения смены email: {otp}\n\nКод действителен 5 минут.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[new_email],
        fail_silently=False,
    )
    logger.info("Email change OTP sent to %s", new_email)


# Время жизни OTP при смене пароля
_PASSWORD_RESET_TTL = 300


def generate_and_store_password_reset_otp(user_id: int) -> str:
    """Генерирует OTP для смены пароля и сохраняет его в Redis."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    _get_redis().setex(f"password_reset_otp:{user_id}", _PASSWORD_RESET_TTL, code)
    return code


def verify_and_consume_password_reset_otp(user_id: int, code: str) -> bool:
    """Проверяет OTP смены пароля и удаляет его при успехе."""
    client = _get_redis()
    key = f"password_reset_otp:{user_id}"
    stored = client.get(key)
    # secrets.compare_digest защищает от timing-атак
    if stored is not None and secrets.compare_digest(stored, code):
        client.delete(key)
        return True
    return False


def send_password_reset_otp(email: str, otp: str) -> None:
    """Отправляет код подтверждения смены пароля на email пользователя."""
    send_mail(
        subject="Подтверждение смены пароля",
        message=f"Ваш код подтверждения смены пароля: {otp}\n\nКод действителен 5 минут.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )
    logger.info("Password reset OTP sent to %s", email)
