"""Тесты сервисного слоя: OTP, pre_auth_token, JWT, email."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from django.core.cache import cache

from apps.users.services import (
    blacklist_refresh_token,
    create_pre_auth_token,
    decode_pre_auth_token,
    generate_and_store_email_change_otp,
    generate_and_store_otp,
    generate_and_store_password_reset_otp,
    issue_token_pair,
    rotate_refresh_token,
    send_email_change_otp,
    send_otp_email,
    send_password_reset_otp,
    verify_and_consume_email_change_otp,
    verify_and_consume_otp,
    verify_and_consume_password_reset_otp,
)

# ---------------------------------------------------------------------------
# Вспомогательные объекты
# ---------------------------------------------------------------------------


def _mock_user(pk: int = 1) -> MagicMock:
    """Возвращает мок пользователя с заданным pk для тестирования JWT."""
    return MagicMock(pk=pk)


def _fresh_token_pair(user_id: int = 42) -> dict[str, str]:
    """Выпускает свежую JWT-пару для переданного user_id без обращения к БД."""
    return issue_token_pair(_mock_user(user_id))


# ---------------------------------------------------------------------------
# OTP для входа
# ---------------------------------------------------------------------------


class TestGenerateAndStoreOtp:
    """Тесты генерации и хранения OTP для входа."""

    def test_returns_six_digit_string(self) -> None:
        """Возвращённый код состоит ровно из 6 цифр."""
        code = generate_and_store_otp(1)
        assert len(code) == 6
        assert code.isdigit()

    def test_otp_stored_in_cache(self) -> None:
        """Сгенерированный OTP сохраняется в кэше под ключом otp:<user_id>."""
        code = generate_and_store_otp(1)
        assert cache.get("otp:1") == code

    def test_each_call_overwrites_previous_code(self) -> None:
        """Повторная генерация перезаписывает предыдущий OTP; в кэше хранится последний."""
        generate_and_store_otp(1)
        second = generate_and_store_otp(1)
        assert cache.get("otp:1") == second


class TestVerifyAndConsumeOtp:
    """Тесты верификации и потребления OTP."""

    def test_valid_code_returns_true(self) -> None:
        """Правильный OTP принимается и функция возвращает True."""
        code = generate_and_store_otp(1)
        assert verify_and_consume_otp(1, code) is True

    def test_valid_code_is_deleted_after_use(self) -> None:
        """После успешной верификации OTP удаляется из кэша (одноразовость)."""
        code = generate_and_store_otp(1)
        verify_and_consume_otp(1, code)
        assert cache.get("otp:1") is None

    def test_wrong_code_returns_false(self) -> None:
        """Неверный OTP отклоняется и возвращается False."""
        generate_and_store_otp(1)
        assert verify_and_consume_otp(1, "000000") is False

    def test_wrong_code_does_not_delete_stored_otp(self) -> None:
        """Неверная попытка верификации не удаляет OTP из кэша."""
        code = generate_and_store_otp(1)
        verify_and_consume_otp(1, "000000")
        assert cache.get("otp:1") == code

    def test_no_otp_stored_returns_false(self) -> None:
        """Если OTP не был сгенерирован, возвращается False."""
        assert verify_and_consume_otp(99, "123456") is False


# ---------------------------------------------------------------------------
# Pre-auth token
# ---------------------------------------------------------------------------


class TestPreAuthToken:
    """Тесты создания и декодирования pre_auth_token первого шага аутентификации."""

    def test_create_and_decode_roundtrip(self) -> None:
        """Созданный токен успешно декодируется и возвращает исходный user_id."""
        token = create_pre_auth_token(42)
        assert decode_pre_auth_token(token) == 42

    def test_tampered_token_raises_value_error(self) -> None:
        """Изменённый токен вызывает ValueError при декодировании."""
        with pytest.raises(ValueError, match="invalid"):
            decode_pre_auth_token("invalid.token.data")

    def test_different_users_get_different_tokens(self) -> None:
        """Токены для разных пользователей не совпадают."""
        token_a = create_pre_auth_token(1)
        token_b = create_pre_auth_token(2)
        assert token_a != token_b


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------


class TestIssueTokenPair:
    """Тесты выпуска JWT-пары."""

    def test_returns_access_and_refresh_keys(self) -> None:
        """Результат содержит ключи access и refresh."""
        tokens = _fresh_token_pair()
        assert "access" in tokens
        assert "refresh" in tokens

    def test_tokens_are_non_empty_strings(self) -> None:
        """Оба токена являются непустыми строками."""
        tokens = _fresh_token_pair()
        assert isinstance(tokens["access"], str)
        assert tokens["access"]
        assert isinstance(tokens["refresh"], str)
        assert tokens["refresh"]


class TestBlacklistRefreshToken:
    """Тесты блэклистинга refresh-токена."""

    def test_blacklisted_token_cannot_be_rotated(self) -> None:
        """После блэклистинга токен нельзя использовать для ротации."""
        tokens = _fresh_token_pair()
        blacklist_refresh_token(tokens["refresh"])
        with pytest.raises(ValueError, match="revoked"):
            rotate_refresh_token(tokens["refresh"])

    def test_fresh_token_is_not_blacklisted(self) -> None:
        """Свежий токен успешно проходит ротацию (не находится в блэклисте)."""
        tokens = _fresh_token_pair()
        new_tokens = rotate_refresh_token(tokens["refresh"])
        assert "access" in new_tokens

    def test_invalid_token_raises_value_error(self) -> None:
        """Попытка блэклистинга невалидного токена вызывает ValueError."""
        with pytest.raises(ValueError, match="Invalid refresh token"):
            blacklist_refresh_token("not.a.token")


class TestRotateRefreshToken:
    """Тесты ротации refresh-токена."""

    def test_rotation_returns_new_token_pair(self) -> None:
        """Ротация возвращает новую пару токенов с ключами access и refresh."""
        tokens = _fresh_token_pair()
        new_tokens = rotate_refresh_token(tokens["refresh"])
        assert "access" in new_tokens
        assert "refresh" in new_tokens

    def test_old_token_is_invalidated_after_rotation(self) -> None:
        """После ротации старый refresh-токен нельзя использовать повторно."""
        tokens = _fresh_token_pair()
        rotate_refresh_token(tokens["refresh"])
        with pytest.raises(ValueError, match="revoked"):
            rotate_refresh_token(tokens["refresh"])

    def test_rotating_blacklisted_token_raises_value_error(self) -> None:
        """Ротация уже отозванного токена вызывает ValueError."""
        tokens = _fresh_token_pair()
        rotate_refresh_token(tokens["refresh"])
        with pytest.raises(ValueError, match="revoked"):
            rotate_refresh_token(tokens["refresh"])

    def test_invalid_token_raises_value_error(self) -> None:
        """Ротация невалидного токена вызывает ValueError."""
        with pytest.raises(ValueError, match="Invalid refresh token"):
            rotate_refresh_token("garbage")


# ---------------------------------------------------------------------------
# Email: отправка OTP
# ---------------------------------------------------------------------------


class TestSendOtpEmail:
    """Тесты отправки email с OTP для входа."""

    def test_email_sent_to_correct_recipient(self, mailoutbox: list) -> None:
        """Письмо отправляется на указанный адрес."""
        send_otp_email("user@example.com", "123456")
        assert len(mailoutbox) == 1
        assert "user@example.com" in mailoutbox[0].to

    def test_email_body_contains_otp(self, mailoutbox: list) -> None:
        """Тело письма содержит переданный OTP-код."""
        send_otp_email("user@example.com", "654321")
        assert "654321" in mailoutbox[0].body


class TestSendEmailChangeOtp:
    """Тесты отправки email с OTP для смены адреса."""

    def test_email_sent_to_new_address(self, mailoutbox: list) -> None:
        """Письмо отправляется на новый email, а не на старый."""
        send_email_change_otp("new@example.com", "111111")
        assert "new@example.com" in mailoutbox[0].to

    def test_email_body_contains_otp(self, mailoutbox: list) -> None:
        """Тело письма содержит переданный OTP-код."""
        send_email_change_otp("new@example.com", "111111")
        assert "111111" in mailoutbox[0].body


class TestSendPasswordResetOtp:
    """Тесты отправки email с OTP для смены пароля."""

    def test_email_sent_to_recipient(self, mailoutbox: list) -> None:
        """Письмо отправляется на указанный адрес."""
        send_password_reset_otp("user@example.com", "999999")
        assert "user@example.com" in mailoutbox[0].to

    def test_email_body_contains_otp(self, mailoutbox: list) -> None:
        """Тело письма содержит переданный OTP-код."""
        send_password_reset_otp("user@example.com", "999999")
        assert "999999" in mailoutbox[0].body


# ---------------------------------------------------------------------------
# OTP смены email
# ---------------------------------------------------------------------------


class TestEmailChangeOtp:
    """Тесты хранения и верификации OTP для смены email."""

    def test_stores_otp_and_new_email_in_cache(self) -> None:
        """OTP и новый адрес сохраняются в кэше после генерации."""
        code = generate_and_store_email_change_otp(1, "new@example.com")
        assert cache.get("email_change_otp:1") == code
        assert cache.get("email_change_pending:1") == "new@example.com"

    def test_valid_code_returns_new_email(self) -> None:
        """Верный OTP возвращает ожидающий новый email."""
        code = generate_and_store_email_change_otp(1, "new@example.com")
        result = verify_and_consume_email_change_otp(1, code)
        assert result == "new@example.com"

    def test_valid_code_clears_cache_entries(self) -> None:
        """После успешной верификации оба ключа удаляются из кэша."""
        code = generate_and_store_email_change_otp(1, "new@example.com")
        verify_and_consume_email_change_otp(1, code)
        assert cache.get("email_change_otp:1") is None
        assert cache.get("email_change_pending:1") is None

    def test_wrong_code_returns_none(self) -> None:
        """Неверный OTP возвращает None."""
        generate_and_store_email_change_otp(1, "new@example.com")
        assert verify_and_consume_email_change_otp(1, "000000") is None

    def test_no_otp_stored_returns_none(self) -> None:
        """Если OTP не был сгенерирован, возвращается None."""
        assert verify_and_consume_email_change_otp(99, "123456") is None


# ---------------------------------------------------------------------------
# OTP смены пароля
# ---------------------------------------------------------------------------


class TestPasswordResetOtp:
    """Тесты хранения и верификации OTP для смены пароля."""

    def test_stores_otp_in_cache(self) -> None:
        """OTP сохраняется в кэше после генерации."""
        code = generate_and_store_password_reset_otp(1)
        assert cache.get("password_reset_otp:1") == code

    def test_valid_code_returns_true(self) -> None:
        """Верный OTP принимается и возвращается True."""
        code = generate_and_store_password_reset_otp(1)
        assert verify_and_consume_password_reset_otp(1, code) is True

    def test_valid_code_is_deleted_after_use(self) -> None:
        """После успешной верификации OTP удаляется из кэша."""
        code = generate_and_store_password_reset_otp(1)
        verify_and_consume_password_reset_otp(1, code)
        assert cache.get("password_reset_otp:1") is None

    def test_wrong_code_returns_false(self) -> None:
        """Неверный OTP отклоняется и возвращается False."""
        generate_and_store_password_reset_otp(1)
        assert verify_and_consume_password_reset_otp(1, "000000") is False

    def test_no_otp_stored_returns_false(self) -> None:
        """Если OTP не был сгенерирован, возвращается False."""
        assert verify_and_consume_password_reset_otp(99, "123456") is False
