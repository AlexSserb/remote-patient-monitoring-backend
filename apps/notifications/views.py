"""Представления системы уведомлений."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.conf import settings
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.notifications.serializers import (
    NotificationScheduleCreateSerializer,
    NotificationScheduleSerializer,
    NotificationScheduleUpdateSerializer,
    PushSubscriptionSerializer,
)
from apps.notifications.services import EmailSubscriptionService, PushSubscriptionService, ScheduleService

if TYPE_CHECKING:
    from rest_framework.request import Request

logger = logging.getLogger(__name__)


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="patient_id",
            type=int,
            location=OpenApiParameter.QUERY,
            required=True,
            description="ID пациента, чьи расписания запрашиваются",
        ),
    ],
    responses={
        200: NotificationScheduleSerializer(many=True),
        400: OpenApiResponse(description="Не передан patient_id"),
        403: OpenApiResponse(description="Нет доступа к расписаниям пациента"),
        404: OpenApiResponse(description="Пациент не найден"),
    },
    summary="Список расписаний уведомлений для пациента",
    tags=["notifications"],
    methods=["GET"],
)
@extend_schema(
    request=NotificationScheduleCreateSerializer,
    responses={
        200: NotificationScheduleSerializer,
        201: NotificationScheduleSerializer,
        400: OpenApiResponse(description="Ошибка валидации"),
        403: OpenApiResponse(description="Нет доступа к пациенту"),
    },
    summary="Создать или обновить расписание уведомлений",
    tags=["notifications"],
    methods=["POST"],
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def schedules_list_create(request: Request) -> Response:
    """Возвращает расписания для пациента или создаёт расписание для текущего пользователя."""
    service = ScheduleService()

    if request.method == "GET":
        patient_id = request.query_params.get("patient_id")
        if not patient_id:
            return Response({"detail": "patient_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        schedules = service.list_schedules(request.user, int(patient_id))
        return Response(NotificationScheduleSerializer(schedules, many=True).data)

    serializer = NotificationScheduleCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    schedule, created = service.upsert_schedule(request.user, serializer.validated_data)
    response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return Response(NotificationScheduleSerializer(schedule).data, status=response_status)


@extend_schema(
    request=NotificationScheduleUpdateSerializer,
    responses={
        200: NotificationScheduleSerializer,
        400: OpenApiResponse(description="Ошибка валидации"),
        403: OpenApiResponse(description="Нет прав на изменение расписания"),
        404: OpenApiResponse(description="Расписание не найдено"),
    },
    summary="Обновить параметры расписания уведомлений",
    tags=["notifications"],
)
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def schedule_detail(request: Request, schedule_id: int) -> Response:
    """Обновляет дни, время и статус активности расписания уведомлений."""
    serializer = NotificationScheduleUpdateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    schedule = ScheduleService().patch_schedule(request.user, schedule_id, serializer.validated_data)
    return Response(NotificationScheduleSerializer(schedule).data)


@extend_schema(
    responses={200: OpenApiResponse(description="Публичный VAPID-ключ для подписки")},
    summary="Публичный VAPID-ключ для web push",
    tags=["notifications"],
    auth=[],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def vapid_public_key(_request: Request) -> Response:
    """Возвращает публичный VAPID-ключ для создания push-подписки в браузере."""
    return Response({"publicKey": settings.VAPID_PUBLIC_KEY})


@extend_schema(
    responses={200: OpenApiResponse(description='{"is_active": bool}')},
    summary="Статус email-уведомлений текущего пользователя",
    tags=["notifications"],
    methods=["GET"],
)
@extend_schema(
    responses={204: OpenApiResponse(description="Email-уведомления включены")},
    summary="Включить email-уведомления",
    tags=["notifications"],
    methods=["POST"],
)
@extend_schema(
    responses={204: OpenApiResponse(description="Email-уведомления отключены")},
    summary="Отключить email-уведомления",
    tags=["notifications"],
    methods=["DELETE"],
)
@api_view(["GET", "POST", "DELETE"])
@permission_classes([IsAuthenticated])
def email_subscription(request: Request) -> Response:
    """Возвращает статус или меняет активность email-уведомлений; user_id позволяет управлять настройками пациента."""
    service = EmailSubscriptionService()
    raw_user_id = request.query_params.get("user_id")
    target = service.resolve_target(request.user, int(raw_user_id) if raw_user_id else None)

    if request.method == "GET":
        return Response({"is_active": service.get_status(target)})
    if request.method == "POST":
        service.enable(target)
        return Response(status=status.HTTP_204_NO_CONTENT)
    service.disable(target)
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    request=PushSubscriptionSerializer,
    responses={
        204: OpenApiResponse(description="Подписка сохранена"),
        400: OpenApiResponse(description="Ошибка валидации"),
    },
    summary="Сохранить web push подписку",
    tags=["notifications"],
    methods=["POST"],
)
@extend_schema(
    responses={204: OpenApiResponse(description="Подписка отключена")},
    summary="Отключить web push подписку",
    tags=["notifications"],
    methods=["DELETE"],
)
@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def push_subscription(request: Request) -> Response:
    """Сохраняет push-подписку браузера или деактивирует её для текущего пользователя."""
    service = PushSubscriptionService()

    if request.method == "DELETE":
        service.remove_subscription(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = PushSubscriptionSerializer(data=request.data)
    if not serializer.is_valid():
        logger.error("push_subscription 400: data=%s errors=%s", request.data, serializer.errors)
        raise ValidationError(serializer.errors)
    service.save_subscription(request.user, serializer.validated_data)
    return Response(status=status.HTTP_204_NO_CONTENT)
