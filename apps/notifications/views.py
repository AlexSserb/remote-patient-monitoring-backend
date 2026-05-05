"""Представления системы уведомлений."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.contrib.auth import get_user_model
from django.db.models import Q, QuerySet
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.notifications.models import NotificationSchedule
from apps.notifications.serializers import (
    NotificationScheduleCreateSerializer,
    NotificationScheduleSerializer,
    NotificationScheduleUpdateSerializer,
)
from apps.users.models import CaregiverPatient, DoctorPatient, Role

if TYPE_CHECKING:
    from rest_framework.request import Request

UserModel = get_user_model()


def _check_patient_access(user: Any, patient: Any) -> None:
    """Проверяет право просмотра расписаний пациента: пациент видит только своё, остальные — прикреплённого."""
    if user.role == Role.PATIENT:
        if user.pk != patient.pk:
            raise PermissionDenied
    elif user.role == Role.CAREGIVER:
        if not CaregiverPatient.objects.filter(caregiver=user, patient=patient).exists():
            raise PermissionDenied
    elif user.role == Role.DOCTOR:
        if not DoctorPatient.objects.filter(doctor=user, patient=patient).exists():
            raise PermissionDenied
    else:
        raise PermissionDenied


def _filter_schedules(user: Any, patient: Any) -> QuerySet[NotificationSchedule]:
    """Возвращает расписания для пациента с фильтрацией по роли текущего пользователя."""
    qs = NotificationSchedule.objects.filter(patient=patient).select_related("recipient")
    if user.role == Role.DOCTOR:
        return qs
    if user.role == Role.CAREGIVER:
        # Опекун видит своё расписание и расписание самого пациента
        return qs.filter(Q(recipient=user) | Q(recipient=patient))
    # Пациент видит только своё расписание
    return qs.filter(recipient=user)


def _can_edit_schedule(user: Any, schedule: NotificationSchedule) -> bool:
    """Проверяет право редактировать расписание: опекун и доктор — через связь с пациентом."""
    patient_id = schedule.patient_id  # ty: ignore[unresolved-attribute]
    if user.role == Role.PATIENT:
        # Пациент редактирует только своё расписание на самого себя
        return user.pk == schedule.recipient_id and user.pk == patient_id  # ty: ignore[unresolved-attribute]
    if user.role == Role.CAREGIVER:
        return CaregiverPatient.objects.filter(caregiver=user, patient_id=patient_id).exists()
    if user.role == Role.DOCTOR:
        return DoctorPatient.objects.filter(doctor=user, patient_id=patient_id).exists()
    return False


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
    user = request.user

    if request.method == "GET":
        patient_id = request.query_params.get("patient_id")
        if not patient_id:
            return Response({"detail": "patient_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        patient = get_object_or_404(UserModel, pk=patient_id, role=Role.PATIENT)
        _check_patient_access(user, patient)
        schedules = _filter_schedules(user, patient)
        return Response(NotificationScheduleSerializer(schedules, many=True).data)

    serializer = NotificationScheduleCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    patient_id = serializer.validated_data["patient_id"]
    patient = get_object_or_404(UserModel, pk=patient_id, role=Role.PATIENT)
    _check_patient_access(user, patient)

    recipient_id = serializer.validated_data.get("recipient_id")
    if recipient_id is not None and recipient_id != user.pk:
        # Создание расписания для пациента от имени другого пользователя
        if recipient_id != patient.pk:
            return Response({"detail": "recipient_id must be patient or self."}, status=status.HTTP_400_BAD_REQUEST)
        if user.role == Role.PATIENT:  # ty: ignore[unresolved-attribute]
            raise PermissionDenied
        recipient = patient
    else:
        # Пациент не может создавать расписание для другого пациента
        if user.role == Role.PATIENT and user.pk != patient.pk:  # ty: ignore[unresolved-attribute]
            raise PermissionDenied
        # Доктор не имеет собственного расписания — только для пациента через recipient_id
        if user.role == Role.DOCTOR:  # ty: ignore[unresolved-attribute]
            return Response({"detail": "Doctors must specify recipient_id."}, status=status.HTTP_400_BAD_REQUEST)
        recipient = user

    schedule, created = NotificationSchedule.objects.get_or_create(
        recipient=recipient,
        patient=patient,
        defaults={
            "days_of_week": serializer.validated_data["days_of_week"],
            "times": serializer.validated_data["times"],
            "is_enabled": serializer.validated_data["is_enabled"],
        },
    )
    if not created:
        schedule.days_of_week = serializer.validated_data["days_of_week"]
        schedule.times = serializer.validated_data["times"]
        schedule.is_enabled = serializer.validated_data["is_enabled"]
        schedule.save()

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
    schedule = get_object_or_404(
        NotificationSchedule.objects.select_related("recipient", "patient"),
        pk=schedule_id,
    )
    if not _can_edit_schedule(request.user, schedule):
        raise PermissionDenied

    serializer = NotificationScheduleUpdateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    data = serializer.validated_data
    if "days_of_week" in data:
        schedule.days_of_week = data["days_of_week"]
    if "times" in data:
        schedule.times = data["times"]
    if "is_enabled" in data:
        schedule.is_enabled = data["is_enabled"]
    schedule.save()

    return Response(NotificationScheduleSerializer(schedule).data)
