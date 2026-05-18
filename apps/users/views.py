"""Представления для двухшаговой аутентификации."""

from __future__ import annotations

from typing import TYPE_CHECKING

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.users.serializers import (
    EditPatientSerializer,
    EmailChangeRequestSerializer,
    EmailChangeVerifySerializer,
    LoginSerializer,
    LogoutSerializer,
    PasswordResetVerifySerializer,
    PatientListItemSerializer,
    TokenRefreshSerializer,
    UpdateProfileSerializer,
    UserProfileSerializer,
    UserShortSerializer,
    VerifyOTPSerializer,
)
from apps.users.services import (
    PatientService,
    UserProfileService,
    generate_and_store_password_reset_otp,
    send_password_reset_otp,
)
from config.permissions import IsDoctor, IsDoctorOrCaregiver

if TYPE_CHECKING:
    from rest_framework.request import Request


@extend_schema(
    request=LoginSerializer,
    responses={200: OpenApiResponse(description="pre_auth_token для второго шага")},
    summary="Шаг 1. Вход по email и паролю",
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
    summary="Шаг 2. Подтверждение OTP",
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
    service = UserProfileService()
    if request.method == "PATCH":
        serializer = UpdateProfileSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = service.update_profile(user_id, serializer.validated_data)
    else:
        user = service.get_user(user_id)
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
    serializer = EmailChangeVerifySerializer(data=request.data, context={"user_id": user_id})
    serializer.is_valid(raise_exception=True)
    user = UserProfileService().apply_email_change(user_id, serializer.validated_data["new_email"])
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
    serializer = PasswordResetVerifySerializer(data=request.data, context={"user_id": user_id})
    serializer.is_valid(raise_exception=True)
    UserProfileService().apply_password_reset(user_id, serializer.validated_data["new_password"])
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    responses={200: UserShortSerializer(many=True)},
    summary="Список докторов",
    tags=["users"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsDoctorOrCaregiver])
def list_doctors(request: Request) -> Response:
    """Возвращает всех докторов системы для использования в фильтрах."""
    doctors = UserProfileService().list_doctors()
    return Response(UserShortSerializer(doctors, many=True).data, status=status.HTTP_200_OK)


@extend_schema(
    responses={200: UserShortSerializer(many=True)},
    summary="Список опекунов",
    tags=["users"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsDoctorOrCaregiver])
def list_caregivers(request: Request) -> Response:
    """Возвращает всех опекунов системы для использования в фильтрах."""
    caregivers = UserProfileService().list_caregivers()
    return Response(UserShortSerializer(caregivers, many=True).data, status=status.HTTP_200_OK)


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
        OpenApiParameter(
            name="doctors",
            type=int,
            many=True,
            required=False,
            description="Фильтр по докторам (повторяемый параметр): пациенты хотя бы одного из указанных докторов.",
        ),
        OpenApiParameter(
            name="caregivers",
            type=int,
            many=True,
            required=False,
            description="Фильтр по опекунам (повторяемый параметр): пациенты хотя бы одного из указанных опекунов.",
        ),
        OpenApiParameter(
            name="diagnoses",
            type=int,
            many=True,
            required=False,
            description="Фильтр по диагнозам (повторяемый параметр): пациенты хотя бы с одним из указанных диагнозов.",
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
@permission_classes([IsAuthenticated, IsDoctorOrCaregiver])
def list_patients(request: Request) -> Response:
    """Возвращает постраничный список пациентов с количеством опекунов для доктора или опекуна."""
    patients, total = PatientService().list_patients(request.user, request.query_params)
    return Response({"count": total, "results": PatientListItemSerializer(patients, many=True).data})


@extend_schema(
    request=EditPatientSerializer,
    responses={
        200: PatientListItemSerializer,
        403: OpenApiResponse(description="Доступ запрещён — только для прикреплённых докторов"),
        404: OpenApiResponse(description="Пациент не найден"),
    },
    summary="Редактирование пациента доктором",
    tags=["users"],
)
@api_view(["PATCH"])
@permission_classes([IsAuthenticated, IsDoctor])
def edit_patient(request: Request, patient_id: int) -> Response:
    """Обновляет диагнозы и список докторов пациента; доступно только прикреплённому доктору."""
    serializer = EditPatientSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    updated_patient = PatientService().edit_patient(request.user, patient_id, serializer.validated_data)
    return Response(PatientListItemSerializer(updated_patient).data, status=status.HTTP_200_OK)
