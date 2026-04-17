"""Представления для двухшаговой аутентификации."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.users.models import Role
from apps.users.serializers import (
    EmailChangeRequestSerializer,
    EmailChangeVerifySerializer,
    LoginSerializer,
    LogoutSerializer,
    PasswordResetVerifySerializer,
    PatientListItemSerializer,
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


@extend_schema(
    operation_id="users_patients_list",
    parameters=[
        OpenApiParameter(
            name="attached",
            type=bool,
            required=False,
            description="Только прикреплённые к текущему доктору пациенты. Для опекунов игнорируется.",
        ),
        OpenApiParameter(
            name="has_caregiver",
            type=str,
            enum=["all", "yes", "no"],
            required=False,
            description="Фильтр по наличию опекуна: all — все, yes — есть опекун, no — нет опекуна.",
        ),
        OpenApiParameter(
            name="search",
            type=str,
            required=False,
            description="Поиск по имени, фамилии или email пациента (регистронезависимый).",
        ),
        OpenApiParameter(name="page", type=int, required=False, description="Номер страницы (начиная с 1)."),
        OpenApiParameter(name="page_size", type=int, required=False, description="Количество записей на странице."),
    ],
    responses={
        200: inline_serializer(
            name="PatientListResponse",
            fields={
                "count": drf_serializers.IntegerField(),
                "results": PatientListItemSerializer(many=True),
            },
        ),
        403: OpenApiResponse(description="Доступ запрещён — только для докторов и опекунов"),
    },
    summary="Список пациентов",
    tags=["users"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_patients(request: Request) -> Response:
    """Возвращает постраничный список пациентов с количеством опекунов для доктора или опекуна."""
    user = request.user
    if user.role not in (Role.DOCTOR, Role.CAREGIVER):
        raise PermissionDenied

    qs = UserModel.objects.filter(role=Role.PATIENT).annotate(
        # distinct=True защищает от дублей строк при последующих JOIN-фильтрах
        caregiver_count=Count("patient_caregivers", distinct=True),
    )

    if user.role == Role.DOCTOR:
        attached_param = request.query_params.get("attached", "false").lower()
        if attached_param == "true":
            qs = qs.filter(patient_doctors__doctor=user)
    else:
        # Опекун видит только своих пациентов
        qs = qs.filter(patient_caregivers__caregiver=user)

    has_caregiver = request.query_params.get("has_caregiver", "all")
    if has_caregiver == "yes":
        qs = qs.filter(caregiver_count__gt=0)
    elif has_caregiver == "no":
        qs = qs.filter(caregiver_count=0)

    search = request.query_params.get("search", "").strip()
    if search:
        qs = qs.filter(Q(first_name__icontains=search) | Q(last_name__icontains=search) | Q(email__icontains=search))

    total = qs.count()

    try:
        page = max(1, int(request.query_params.get("page", 1)))
        page_size = min(100, max(1, int(request.query_params.get("page_size", 20))))
    except ValueError:
        page, page_size = 1, 20

    start = (page - 1) * page_size
    patients = qs.order_by("last_name", "first_name")[start : start + page_size]

    return Response(
        {"count": total, "results": PatientListItemSerializer(patients, many=True).data},
        status=status.HTTP_200_OK,
    )
