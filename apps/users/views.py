"""Представления для двухшаговой аутентификации."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.users.serializers import (
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
from apps.users.services import generate_and_store_password_reset_otp, send_password_reset_otp

if TYPE_CHECKING:
    from rest_framework.request import Request

UserModel = get_user_model()


@extend_schema(
    request=LoginSerializer,
    responses={200: OpenApiResponse(description="pre_auth_token для второго шага")},
    summary="Шаг 1 — вход по email и паролю",
    tags=["auth"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
def login(request: Request) -> Response:
    """Принимает email и пароль, отправляет OTP на почту, возвращает pre_auth_token."""
    serializer = LoginSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    return Response(serializer.validated_data, status=status.HTTP_200_OK)


@extend_schema(
    request=VerifyOTPSerializer,
    responses={200: OpenApiResponse(description="access и refresh JWT-токены")},
    summary="Шаг 2 — подтверждение OTP",
    tags=["auth"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
def verify_otp(request: Request) -> Response:
    """Принимает pre_auth_token и OTP, возвращает JWT access и refresh токены."""
    serializer = VerifyOTPSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    return Response(serializer.validated_data, status=status.HTTP_200_OK)


@extend_schema(
    request=TokenRefreshSerializer,
    responses={200: OpenApiResponse(description="Новые access и refresh токены")},
    summary="Обновление JWT-токенов",
    tags=["auth"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
def token_refresh(request: Request) -> Response:
    """Инвалидирует старый refresh-токен и выпускает новую пару."""
    serializer = TokenRefreshSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    return Response(serializer.validated_data, status=status.HTTP_200_OK)


@extend_schema(
    request=LogoutSerializer,
    responses={204: OpenApiResponse(description="Успешный выход")},
    summary="Выход из системы",
    tags=["auth"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request: Request) -> Response:
    """Добавляет refresh-токен в Redis-блэклист и завершает сессию."""
    serializer = LogoutSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    responses={
        200: UserProfileSerializer,
        403: OpenApiResponse(description="Доступ запрещён"),
        404: OpenApiResponse(description="Пользователь не найден"),
    },
    methods=["GET"],
    summary="Профиль пользователя",
    tags=["users"],
)
@extend_schema(
    request=UpdateProfileSerializer,
    responses={
        200: UserProfileSerializer,
        403: OpenApiResponse(description="Доступ запрещён"),
        404: OpenApiResponse(description="Пользователь не найден"),
    },
    methods=["PATCH"],
    summary="Обновление имени и фамилии",
    tags=["users"],
)
@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def get_user(request: Request, user_id: int) -> Response:
    """Возвращает или обновляет профиль пользователя; доступен только владельцу аккаунта."""
    if request.user.pk != user_id:
        raise PermissionDenied
    user = UserModel.objects.get(pk=user_id)
    if request.method == "PATCH":
        serializer = UpdateProfileSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
    return Response(UserProfileSerializer(user).data, status=status.HTTP_200_OK)


@extend_schema(
    request=EmailChangeRequestSerializer,
    responses={
        204: OpenApiResponse(description="OTP отправлен на новый email"),
        403: OpenApiResponse(description="Доступ запрещён"),
    },
    summary="Запрос смены email",
    tags=["users"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def request_email_change(request: Request, user_id: int) -> Response:
    """Проверяет новый email на уникальность и отправляет OTP для подтверждения."""
    if request.user.pk != user_id:
        raise PermissionDenied
    serializer = EmailChangeRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save(user=request.user)
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    request=EmailChangeVerifySerializer,
    responses={
        200: UserProfileSerializer,
        403: OpenApiResponse(description="Доступ запрещён"),
    },
    summary="Подтверждение смены email",
    tags=["users"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def verify_email_change(request: Request, user_id: int) -> Response:
    """Проверяет OTP и применяет новый email к аккаунту пользователя."""
    if request.user.pk != user_id:
        raise PermissionDenied
    user = UserModel.objects.get(pk=user_id)
    serializer = EmailChangeVerifySerializer(data=request.data, context={"user": user})
    serializer.is_valid(raise_exception=True)
    user.email = serializer.validated_data["new_email"]
    user.save(update_fields=["email"])
    return Response(UserProfileSerializer(user).data, status=status.HTTP_200_OK)


@extend_schema(
    request=None,
    responses={
        204: OpenApiResponse(description="OTP отправлен на email пользователя"),
        403: OpenApiResponse(description="Доступ запрещён"),
    },
    summary="Запрос смены пароля",
    tags=["users"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def request_password_reset(request: Request, user_id: int) -> Response:
    """Генерирует OTP и отправляет его на текущий email пользователя."""
    if request.user.pk != user_id:
        raise PermissionDenied
    otp = generate_and_store_password_reset_otp(user_id)
    send_password_reset_otp(request.user.email, otp)
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    request=PasswordResetVerifySerializer,
    responses={
        204: OpenApiResponse(description="Пароль успешно изменён"),
        403: OpenApiResponse(description="Доступ запрещён"),
    },
    summary="Подтверждение смены пароля",
    tags=["users"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def verify_password_reset(request: Request, user_id: int) -> Response:
    """Проверяет OTP и устанавливает новый пароль пользователя."""
    if request.user.pk != user_id:
        raise PermissionDenied
    user = UserModel.objects.get(pk=user_id)
    serializer = PasswordResetVerifySerializer(data=request.data, context={"user": user})
    serializer.is_valid(raise_exception=True)
    user.set_password(serializer.validated_data["new_password"])
    user.save(update_fields=["password"])
    return Response(status=status.HTTP_204_NO_CONTENT)
