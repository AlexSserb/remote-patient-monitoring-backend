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

from users.serializers import (
    LoginSerializer,
    LogoutSerializer,
    TokenRefreshSerializer,
    UserProfileSerializer,
    VerifyOTPSerializer,
)

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
    summary="Профиль пользователя",
    tags=["users"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_user(request: Request, user_id: int) -> Response:
    """Возвращает профиль пользователя; доступен только владельцу аккаунта."""
    if request.user.pk != user_id:
        raise PermissionDenied
    user = UserModel.objects.get(pk=user_id)
    serializer = UserProfileSerializer(user)
    return Response(serializer.data, status=status.HTTP_200_OK)
