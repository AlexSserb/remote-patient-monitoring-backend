"""Тесты API-эндпоинтов через APIClient."""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from users.models import User
from users.services import (
    create_pre_auth_token,
    generate_and_store_email_change_otp,
    generate_and_store_otp,
    generate_and_store_password_reset_otp,
    issue_token_pair,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Аутентификация: вход
# ---------------------------------------------------------------------------


class TestLogin:
    """Тесты первого шага входа (email + пароль)."""

    def test_valid_credentials_return_200_and_pre_auth_token(
        self, api_client: APIClient, user: User, mailoutbox: list
    ) -> None:
        """Верные учётные данные возвращают pre_auth_token и отправляют OTP."""
        response = api_client.post(
            reverse("auth-login"),
            {"email": user.email, "password": "SecurePass123!"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert "pre_auth_token" in response.data
        assert len(mailoutbox) == 1

    def test_wrong_password_returns_400(self, api_client: APIClient, user: User) -> None:
        """Неверный пароль возвращает 400."""
        response = api_client.post(
            reverse("auth-login"),
            {"email": user.email, "password": "WrongPass!"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_nonexistent_user_returns_400(self, api_client: APIClient) -> None:
        """Несуществующий email возвращает 400."""
        response = api_client.post(
            reverse("auth-login"),
            {"email": "nobody@example.com", "password": "Pass123!"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Аутентификация: верификация OTP
# ---------------------------------------------------------------------------


class TestVerifyOtp:
    """Тесты второго шага входа — верификации OTP."""

    def test_valid_otp_returns_jwt_pair(self, api_client: APIClient, user: User) -> None:
        """Верный OTP возвращает access и refresh токены."""
        pre_auth_token = create_pre_auth_token(user.pk)
        otp = generate_and_store_otp(user.pk)
        response = api_client.post(
            reverse("auth-verify-otp"),
            {"pre_auth_token": pre_auth_token, "otp": otp},
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data

    def test_wrong_otp_returns_400(self, api_client: APIClient, user: User) -> None:
        """Неверный OTP возвращает 400."""
        pre_auth_token = create_pre_auth_token(user.pk)
        generate_and_store_otp(user.pk)
        response = api_client.post(
            reverse("auth-verify-otp"),
            {"pre_auth_token": pre_auth_token, "otp": "000000"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_pre_auth_token_returns_400(self, api_client: APIClient, user: User) -> None:
        """Невалидный pre_auth_token возвращает 400."""
        otp = generate_and_store_otp(user.pk)
        response = api_client.post(
            reverse("auth-verify-otp"),
            {"pre_auth_token": "bad.token", "otp": otp},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Аутентификация: обновление токена
# ---------------------------------------------------------------------------


class TestTokenRefresh:
    """Тесты ротации refresh-токена."""

    def test_valid_refresh_returns_new_pair(self, api_client: APIClient, user: User) -> None:
        """Валидный refresh-токен возвращает новую пару JWT."""
        tokens = issue_token_pair(user)
        response = api_client.post(
            reverse("auth-token-refresh"),
            {"refresh": tokens["refresh"]},
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data

    def test_reused_refresh_token_returns_400(self, api_client: APIClient, user: User) -> None:
        """Повторное использование refresh-токена возвращает 400 (блэклист)."""
        tokens = issue_token_pair(user)
        api_client.post(reverse("auth-token-refresh"), {"refresh": tokens["refresh"]})
        response = api_client.post(reverse("auth-token-refresh"), {"refresh": tokens["refresh"]})
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Аутентификация: выход
# ---------------------------------------------------------------------------


class TestLogout:
    """Тесты выхода из системы."""

    def test_logout_blacklists_token_and_returns_204(self, auth_client: APIClient, user: User) -> None:
        """Выход добавляет refresh-токен в блэклист и возвращает 204."""
        tokens = issue_token_pair(user)
        response = auth_client.post(reverse("auth-logout"), {"refresh": tokens["refresh"]})
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_logout_requires_authentication(self, api_client: APIClient, user: User) -> None:
        """Выход без токена аутентификации возвращает 401."""
        tokens = issue_token_pair(user)
        response = api_client.post(reverse("auth-logout"), {"refresh": tokens["refresh"]})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Профиль пользователя
# ---------------------------------------------------------------------------


class TestGetUser:
    """Тесты получения и обновления профиля."""

    def test_get_own_profile_returns_200(self, auth_client: APIClient, user: User) -> None:
        """Авторизованный пользователь получает свой профиль."""
        response = auth_client.get(reverse("users-profile", kwargs={"user_id": user.pk}))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == user.email

    def test_get_other_users_profile_returns_403(self, auth_client: APIClient, other_user: User) -> None:
        """Попытка получить чужой профиль возвращает 403."""
        response = auth_client.get(reverse("users-profile", kwargs={"user_id": other_user.pk}))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_get_returns_401(self, api_client: APIClient, user: User) -> None:
        """Запрос без токена возвращает 401."""
        response = api_client.get(reverse("users-profile", kwargs={"user_id": user.pk}))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_patch_own_profile_returns_200_with_updated_data(self, auth_client: APIClient, user: User) -> None:
        """Обновление собственного профиля возвращает 200 с изменёнными данными."""
        response = auth_client.patch(
            reverse("users-profile", kwargs={"user_id": user.pk}),
            {"first_name": "Алексей", "last_name": "Смирнов"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["first_name"] == "Алексей"
        assert response.data["last_name"] == "Смирнов"

    def test_patch_other_users_profile_returns_403(self, auth_client: APIClient, other_user: User) -> None:
        """Попытка изменить чужой профиль возвращает 403."""
        response = auth_client.patch(
            reverse("users-profile", kwargs={"user_id": other_user.pk}),
            {"first_name": "Хакер"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# Смена email
# ---------------------------------------------------------------------------


class TestEmailChange:
    """Тесты запроса и подтверждения смены email."""

    def test_request_email_change_returns_204(self, auth_client: APIClient, user: User, mailoutbox: list) -> None:
        """Запрос на смену email отправляет OTP и возвращает 204."""
        response = auth_client.post(
            reverse("email-change-request", kwargs={"user_id": user.pk}),
            {"new_email": "new@example.com"},
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert len(mailoutbox) == 1

    def test_request_email_change_for_other_user_returns_403(self, auth_client: APIClient, other_user: User) -> None:
        """Попытка сменить email другого пользователя возвращает 403."""
        response = auth_client.post(
            reverse("email-change-request", kwargs={"user_id": other_user.pk}),
            {"new_email": "hacked@example.com"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_verify_email_change_updates_email_and_returns_200(self, auth_client: APIClient, user: User) -> None:
        """Верный OTP меняет email пользователя и возвращает обновлённый профиль."""
        new_email = "verified@example.com"
        code = generate_and_store_email_change_otp(user.pk, new_email)
        response = auth_client.post(
            reverse("email-change-verify", kwargs={"user_id": user.pk}),
            {"otp": code},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == new_email
        user.refresh_from_db()
        assert user.email == new_email

    def test_verify_email_change_with_wrong_otp_returns_400(self, auth_client: APIClient, user: User) -> None:
        """Неверный OTP при верификации смены email возвращает 400."""
        generate_and_store_email_change_otp(user.pk, "verified@example.com")
        response = auth_client.post(
            reverse("email-change-verify", kwargs={"user_id": user.pk}),
            {"otp": "000000"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Смена пароля
# ---------------------------------------------------------------------------


class TestPasswordReset:
    """Тесты запроса и подтверждения смены пароля."""

    def test_request_password_reset_sends_otp_and_returns_204(
        self, auth_client: APIClient, user: User, mailoutbox: list
    ) -> None:
        """Запрос на смену пароля отправляет OTP и возвращает 204."""
        response = auth_client.post(reverse("password-reset-request", kwargs={"user_id": user.pk}))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert len(mailoutbox) == 1

    def test_request_password_reset_for_other_user_returns_403(self, auth_client: APIClient, other_user: User) -> None:
        """Попытка запросить сброс пароля другого пользователя возвращает 403."""
        response = auth_client.post(reverse("password-reset-request", kwargs={"user_id": other_user.pk}))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_verify_password_reset_updates_password_and_returns_204(self, auth_client: APIClient, user: User) -> None:
        """Верный OTP и новый пароль меняют пароль пользователя и возвращают 204."""
        new_password = "BrandNewPass789!"
        code = generate_and_store_password_reset_otp(user.pk)
        response = auth_client.post(
            reverse("password-reset-verify", kwargs={"user_id": user.pk}),
            {"otp": code, "new_password": new_password},
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        user.refresh_from_db()
        assert user.check_password(new_password) is True

    def test_verify_password_reset_with_wrong_otp_returns_400(self, auth_client: APIClient, user: User) -> None:
        """Неверный OTP при верификации смены пароля возвращает 400."""
        generate_and_store_password_reset_otp(user.pk)
        response = auth_client.post(
            reverse("password-reset-verify", kwargs={"user_id": user.pk}),
            {"otp": "000000", "new_password": "BrandNewPass789!"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
