"""Тесты сериализаторов: логика валидации и side-эффекты."""

from __future__ import annotations

import pytest
from django.core.cache import cache

from users.models import Role, User
from users.serializers import (
    EmailChangeRequestSerializer,
    EmailChangeVerifySerializer,
    LoginSerializer,
    LogoutSerializer,
    PasswordResetVerifySerializer,
    TokenRefreshSerializer,
    UpdateProfileSerializer,
    UserProfileSerializer,
    VerifyOTPSerializer,
)
from users.services import (
    create_pre_auth_token,
    generate_and_store_email_change_otp,
    generate_and_store_otp,
    generate_and_store_password_reset_otp,
    issue_token_pair,
    rotate_refresh_token,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# LoginSerializer
# ---------------------------------------------------------------------------


class TestLoginSerializer:
    """Тесты первого шага аутентификации."""

    def test_valid_credentials_return_pre_auth_token(self, user: User, mailoutbox: list) -> None:
        """Верные учётные данные возвращают pre_auth_token и отправляют OTP-письмо."""
        serializer = LoginSerializer(data={"email": user.email, "password": "SecurePass123!"})
        assert serializer.is_valid()
        assert "pre_auth_token" in serializer.validated_data
        assert len(mailoutbox) == 1

    def test_wrong_password_is_invalid(self, user: User) -> None:
        """Неверный пароль делает сериализатор невалидным."""
        serializer = LoginSerializer(data={"email": user.email, "password": "WrongPass!"})
        assert not serializer.is_valid()

    def test_inactive_user_is_rejected(self, user: User) -> None:
        """Отключённая учётная запись отклоняется при валидации."""
        user.is_active = False
        user.save(update_fields=["is_active"])
        serializer = LoginSerializer(data={"email": user.email, "password": "SecurePass123!"})
        assert not serializer.is_valid()

    def test_otp_stored_in_cache_after_valid_login(self, user: User, mailoutbox: list) -> None:
        """После успешного входа OTP сохраняется в кэше."""
        serializer = LoginSerializer(data={"email": user.email, "password": "SecurePass123!"})
        serializer.is_valid()
        assert cache.get(f"otp:{user.pk}") is not None


# ---------------------------------------------------------------------------
# VerifyOTPSerializer
# ---------------------------------------------------------------------------


class TestVerifyOTPSerializer:
    """Тесты второго шага аутентификации — верификации OTP."""

    def test_valid_otp_returns_jwt_pair(self, user: User) -> None:
        """Верный OTP и токен возвращают пару JWT."""
        pre_auth_token = create_pre_auth_token(user.pk)
        otp = generate_and_store_otp(user.pk)
        serializer = VerifyOTPSerializer(data={"pre_auth_token": pre_auth_token, "otp": otp})
        assert serializer.is_valid()
        assert "access" in serializer.validated_data
        assert "refresh" in serializer.validated_data

    def test_invalid_pre_auth_token_is_rejected(self, user: User) -> None:
        """Невалидный pre_auth_token вызывает ошибку валидации."""
        otp = generate_and_store_otp(user.pk)
        serializer = VerifyOTPSerializer(data={"pre_auth_token": "bad.token", "otp": otp})
        assert not serializer.is_valid()

    def test_wrong_otp_is_rejected(self, user: User) -> None:
        """Неверный OTP вызывает ошибку валидации."""
        pre_auth_token = create_pre_auth_token(user.pk)
        generate_and_store_otp(user.pk)
        serializer = VerifyOTPSerializer(data={"pre_auth_token": pre_auth_token, "otp": "000000"})
        assert not serializer.is_valid()

    def test_otp_consumed_after_successful_verify(self, user: User) -> None:
        """После успешной верификации OTP удаляется из кэша."""
        pre_auth_token = create_pre_auth_token(user.pk)
        otp = generate_and_store_otp(user.pk)
        serializer = VerifyOTPSerializer(data={"pre_auth_token": pre_auth_token, "otp": otp})
        serializer.is_valid()
        assert cache.get(f"otp:{user.pk}") is None


# ---------------------------------------------------------------------------
# TokenRefreshSerializer
# ---------------------------------------------------------------------------


class TestTokenRefreshSerializer:
    """Тесты ротации refresh-токена."""

    def test_valid_refresh_token_returns_new_pair(self, user: User) -> None:
        """Валидный refresh-токен возвращает новую пару JWT."""
        tokens = issue_token_pair(user)
        serializer = TokenRefreshSerializer(data={"refresh": tokens["refresh"]})
        assert serializer.is_valid()
        assert "access" in serializer.validated_data
        assert "refresh" in serializer.validated_data

    def test_blacklisted_token_is_rejected(self, user: User) -> None:
        """Отозванный refresh-токен вызывает ошибку валидации."""
        tokens = issue_token_pair(user)
        # Первое использование — токен попадает в блэклист
        TokenRefreshSerializer(data={"refresh": tokens["refresh"]}).is_valid()
        # Повторное использование должно быть отклонено
        serializer = TokenRefreshSerializer(data={"refresh": tokens["refresh"]})
        assert not serializer.is_valid()

    def test_invalid_token_is_rejected(self) -> None:
        """Невалидная строка токена вызывает ошибку валидации."""
        serializer = TokenRefreshSerializer(data={"refresh": "not.a.token"})
        assert not serializer.is_valid()


# ---------------------------------------------------------------------------
# UserProfileSerializer
# ---------------------------------------------------------------------------


class TestUserProfileSerializer:
    """Тесты сериализатора профиля пользователя."""

    def test_contains_expected_fields(self, user: User) -> None:
        """Сериализованные данные содержат все ожидаемые поля."""
        data = UserProfileSerializer(user).data
        assert set(data.keys()) == {"id", "email", "first_name", "last_name", "role", "date_joined"}

    def test_email_matches_user(self, user: User) -> None:
        """Email в сериализованных данных совпадает с email пользователя."""
        data = UserProfileSerializer(user).data
        assert data["email"] == user.email

    def test_role_value_is_string(self, user: User) -> None:
        """Роль передаётся как строковое значение."""
        data = UserProfileSerializer(user).data
        assert data["role"] == Role.PATIENT


# ---------------------------------------------------------------------------
# UpdateProfileSerializer
# ---------------------------------------------------------------------------


class TestUpdateProfileSerializer:
    """Тесты сериализатора обновления имени и фамилии."""

    def test_updates_first_and_last_name(self, user: User) -> None:
        """Сериализатор сохраняет новые имя и фамилию."""
        serializer = UpdateProfileSerializer(
            user,
            data={"first_name": "Алексей", "last_name": "Алексеев"},
            partial=True,
        )
        assert serializer.is_valid()
        updated = serializer.save()
        assert updated.first_name == "Алексей"
        assert updated.last_name == "Алексеев"

    def test_partial_update_only_first_name(self, user: User) -> None:
        """Частичное обновление меняет только переданное поле."""
        original_last = user.last_name
        serializer = UpdateProfileSerializer(user, data={"first_name": "Новое"}, partial=True)
        assert serializer.is_valid()
        updated = serializer.save()
        assert updated.first_name == "Новое"
        assert updated.last_name == original_last


# ---------------------------------------------------------------------------
# EmailChangeRequestSerializer
# ---------------------------------------------------------------------------


class TestEmailChangeRequestSerializer:
    """Тесты запроса на смену email."""

    def test_valid_new_email_sends_otp(self, user: User, mailoutbox: list) -> None:
        """Запрос на смену email генерирует OTP и отправляет его на новый адрес."""
        serializer = EmailChangeRequestSerializer(data={"new_email": "newemail@example.com"})
        assert serializer.is_valid()
        serializer.save(user=user)
        assert len(mailoutbox) == 1
        assert "newemail@example.com" in mailoutbox[0].to

    def test_existing_email_is_rejected(self, other_user: User) -> None:
        """Email, уже занятый другим пользователем, не принимается."""
        serializer = EmailChangeRequestSerializer(data={"new_email": other_user.email})
        assert not serializer.is_valid()


# ---------------------------------------------------------------------------
# EmailChangeVerifySerializer
# ---------------------------------------------------------------------------


class TestEmailChangeVerifySerializer:
    """Тесты подтверждения смены email."""

    def test_valid_otp_returns_new_email_in_validated_data(self, user: User) -> None:
        """Верный OTP помещает новый email в validated_data для применения."""
        code = generate_and_store_email_change_otp(user.pk, "confirmed@example.com")
        serializer = EmailChangeVerifySerializer(data={"otp": code}, context={"user": user})
        assert serializer.is_valid()
        assert serializer.validated_data["new_email"] == "confirmed@example.com"

    def test_wrong_otp_is_rejected(self, user: User) -> None:
        """Неверный OTP вызывает ошибку валидации."""
        generate_and_store_email_change_otp(user.pk, "confirmed@example.com")
        serializer = EmailChangeVerifySerializer(data={"otp": "000000"}, context={"user": user})
        assert not serializer.is_valid()

    def test_email_taken_between_request_and_verify_is_rejected(self, user: User, other_user: User) -> None:
        """Если новый email занял другой пользователь за время TTL — верификация отклоняется."""
        code = generate_and_store_email_change_otp(user.pk, other_user.email)
        serializer = EmailChangeVerifySerializer(data={"otp": code}, context={"user": user})
        assert not serializer.is_valid()


# ---------------------------------------------------------------------------
# PasswordResetVerifySerializer
# ---------------------------------------------------------------------------


class TestPasswordResetVerifySerializer:
    """Тесты подтверждения смены пароля."""

    def test_valid_otp_and_password_passes_validation(self, user: User) -> None:
        """Верный OTP и надёжный пароль проходят валидацию."""
        code = generate_and_store_password_reset_otp(user.pk)
        serializer = PasswordResetVerifySerializer(
            data={"otp": code, "new_password": "NewSecurePass456!"},
            context={"user": user},
        )
        assert serializer.is_valid()

    def test_wrong_otp_is_rejected(self, user: User) -> None:
        """Неверный OTP вызывает ошибку валидации."""
        generate_and_store_password_reset_otp(user.pk)
        serializer = PasswordResetVerifySerializer(
            data={"otp": "000000", "new_password": "NewSecurePass456!"},
            context={"user": user},
        )
        assert not serializer.is_valid()

    def test_weak_password_is_rejected(self, user: User) -> None:
        """Слабый пароль отклоняется валидаторами Django независимо от OTP."""
        code = generate_and_store_password_reset_otp(user.pk)
        serializer = PasswordResetVerifySerializer(
            data={"otp": code, "new_password": "123"},
            context={"user": user},
        )
        assert not serializer.is_valid()


# ---------------------------------------------------------------------------
# LogoutSerializer
# ---------------------------------------------------------------------------


class TestLogoutSerializer:
    """Тесты сериализатора выхода из системы."""

    def test_valid_refresh_token_is_accepted(self, user: User) -> None:
        """Валидный refresh-токен принимается — последующая ротация невозможна."""
        tokens = issue_token_pair(user)
        serializer = LogoutSerializer(data={"refresh": tokens["refresh"]})
        assert serializer.is_valid()
        with pytest.raises(ValueError, match="revoked"):
            rotate_refresh_token(tokens["refresh"])

    def test_invalid_token_is_rejected(self) -> None:
        """Невалидный refresh-токен вызывает ошибку валидации."""
        serializer = LogoutSerializer(data={"refresh": "garbage"})
        assert not serializer.is_valid()
