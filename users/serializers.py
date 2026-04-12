"""Сериализаторы для двухшаговой аутентификации."""

from __future__ import annotations

from typing import Any, ClassVar

from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers

from users.services import (
    blacklist_refresh_token,
    create_pre_auth_token,
    decode_pre_auth_token,
    generate_and_store_otp,
    issue_token_pair,
    rotate_refresh_token,
    send_otp_email,
    verify_and_consume_otp,
)

UserModel = get_user_model()


class LoginSerializer(serializers.Serializer):
    """Сериализатор первого шага: проверяет пароль, отправляет OTP, возвращает pre_auth_token."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs: dict[str, Any]) -> dict[str, str]:
        """Аутентифицирует пользователя, генерирует OTP и возвращает pre_auth_token."""
        user = authenticate(
            request=self.context.get("request"),
            email=attrs["email"],
            password=attrs["password"],
        )
        if user is None:
            msg = "Неверный email или пароль."
            raise serializers.ValidationError(msg, code="invalid_credentials")
        if not user.is_active:
            msg = "Учётная запись отключена."
            raise serializers.ValidationError(msg, code="inactive_user")

        otp = generate_and_store_otp(user.pk)
        send_otp_email(user.email, otp)

        return {"pre_auth_token": create_pre_auth_token(user.pk)}


class VerifyOTPSerializer(serializers.Serializer):
    """Сериализатор второго шага: проверяет OTP и выдаёт JWT-пару."""

    pre_auth_token = serializers.CharField()
    otp = serializers.CharField(min_length=6, max_length=6)

    def validate(self, attrs: dict[str, Any]) -> dict[str, str]:
        """Верифицирует pre_auth_token и OTP, возвращает access и refresh токены."""
        try:
            user_id = decode_pre_auth_token(attrs["pre_auth_token"])
        except ValueError as exc:
            raise serializers.ValidationError(str(exc), code="invalid_pre_auth_token") from exc

        if not verify_and_consume_otp(user_id, attrs["otp"]):
            msg = "Неверный или истёкший OTP-код."
            raise serializers.ValidationError(msg, code="invalid_otp")

        try:
            user = UserModel.objects.get(pk=user_id)
        except UserModel.DoesNotExist as exc:
            msg = "Пользователь не найден."
            raise serializers.ValidationError(msg, code="user_not_found") from exc

        return issue_token_pair(user)


class TokenRefreshSerializer(serializers.Serializer):
    """Сериализатор ротации токенов: инвалидирует старый refresh, выпускает новую пару."""

    refresh = serializers.CharField()

    def validate(self, attrs: dict[str, Any]) -> dict[str, str]:
        """Инвалидирует старый refresh-токен и возвращает новую JWT-пару."""
        try:
            return rotate_refresh_token(attrs["refresh"])
        except ValueError as exc:
            raise serializers.ValidationError(str(exc), code="invalid_refresh_token") from exc


class UserProfileSerializer(serializers.ModelSerializer):
    """Сериализатор профиля пользователя для отображения публичных данных."""

    class Meta:
        """Метаданные сериализатора профиля."""

        model = UserModel
        fields = ["id", "email", "first_name", "last_name", "role", "date_joined"]


class LogoutSerializer(serializers.Serializer):
    """Сериализатор выхода из системы: добавляет refresh-токен в Redis-блэклист."""

    refresh = serializers.CharField()

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Помещает refresh-токен в чёрный список Redis."""
        try:
            blacklist_refresh_token(attrs["refresh"])
        except ValueError as exc:
            raise serializers.ValidationError(str(exc), code="invalid_refresh_token") from exc
        return attrs
