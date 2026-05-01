"""Представления приложения diagnoses."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from django.db.models import BooleanField, FloatField, IntegerField, Max, Min
from django.db.models.functions import Cast
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from apps.diagnoses.models import Diagnosis, DiaryEntry, DiaryEntryValue, Metric
from apps.diagnoses.serializers import (
    DiagnosisShortSerializer,
    DiaryEntryCreateSerializer,
    DiaryEntryInfo,
    DiaryFieldSerializer,
)
from apps.users.models import CaregiverPatient, Role, User

if TYPE_CHECKING:
    from rest_framework.request import Request


@extend_schema(
    responses={
        200: DiagnosisShortSerializer(many=True),
        403: OpenApiResponse(description="Доступ запрещён — только для докторов и опекунов"),
    },
    summary="Список диагнозов",
    tags=["diagnoses"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_diagnoses(request: Request) -> Response:
    """Возвращает все диагнозы системы для использования в фильтрах."""
    if request.user.role not in (Role.DOCTOR, Role.CAREGIVER):
        raise PermissionDenied
    diagnoses = Diagnosis.objects.order_by("code")
    return Response(DiagnosisShortSerializer(diagnoses, many=True).data, status=status.HTTP_200_OK)


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="patient_id",
            type=int,
            location=OpenApiParameter.QUERY,
            description="ID пациента — обязателен для опекуна, игнорируется для пациента",
            required=False,
        ),
    ],
    responses={
        200: DiaryFieldSerializer(many=True),
        400: OpenApiResponse(description="Не передан patient_id (для опекуна)"),
        403: OpenApiResponse(description="Доступ запрещён или опекун не закреплён за пациентом"),
        404: OpenApiResponse(description="Пациент не найден"),
    },
    summary="Поля дневника для пациента",
    tags=["diagnoses"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_diary_fields(request: Request) -> Response:
    """Возвращает уникальные поля дневника, агрегированные по всем диагнозам пациента."""
    user = request.user

    if user.role == Role.PATIENT:
        patient = user
    elif user.role == Role.CAREGIVER:
        raw_id = request.query_params.get("patient_id")
        if not raw_id:
            return Response({"detail": "patient_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            patient_id = int(raw_id)
        except ValueError:
            return Response({"detail": "patient_id must be an integer"}, status=status.HTTP_400_BAD_REQUEST)
        if not CaregiverPatient.objects.filter(caregiver=user, patient_id=patient_id).exists():
            raise PermissionDenied
        patient = get_object_or_404(User, id=patient_id, role=Role.PATIENT)
    else:
        raise PermissionDenied

    metrics = (
        Metric.objects.filter(diagnosis_metrics__diagnosis__patient_diagnoses__patient=patient)
        .annotate(
            is_required=Cast(
                Max(Cast("diagnosis_metrics__is_required", output_field=IntegerField())),
                output_field=BooleanField(),
            ),
            min_value=Max("diagnosis_metrics__min_value", output_field=FloatField()),
            max_value=Min("diagnosis_metrics__max_value", output_field=FloatField()),
        )
        .order_by("name")
    )

    return Response(DiaryFieldSerializer(metrics, many=True).data, status=status.HTTP_200_OK)


def _resolve_patient_for_diary(request: Request, patient_id_raw: str | None) -> User:
    """Определяет пациента по роли пользователя; опекун обязан передать patient_id."""
    user = request.user
    if user.role == Role.PATIENT:
        return user
    if user.role == Role.CAREGIVER:
        if not patient_id_raw:
            raise ValidationError({"patient_id": "patient_id is required for caregivers"})
        try:
            patient_id = int(patient_id_raw)
        except ValueError:
            raise ValidationError({"patient_id": "patient_id must be an integer"}) from None
        if not CaregiverPatient.objects.filter(caregiver=user, patient_id=patient_id).exists():
            raise PermissionDenied
        return get_object_or_404(User, id=patient_id, role=Role.PATIENT)
    raise PermissionDenied


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                name="patient_id",
                type=int,
                location=OpenApiParameter.QUERY,
                description="ID пациента — обязателен для опекуна, игнорируется для пациента",
                required=False,
            ),
        ],
        responses={
            200: DiaryEntryInfo(many=True),
            400: OpenApiResponse(description="Не передан patient_id (для опекуна)"),
            403: OpenApiResponse(description="Доступ запрещён"),
        },
        summary="Список записей дневника",
        tags=["diagnoses"],
    ),
    create=extend_schema(
        parameters=[
            OpenApiParameter(
                name="patient_id",
                type=int,
                location=OpenApiParameter.QUERY,
                description="ID пациента — обязателен для опекуна",
                required=False,
            ),
        ],
        request=DiaryEntryCreateSerializer,
        responses={
            201: DiaryEntryInfo,
            400: OpenApiResponse(description="Ошибка валидации"),
            403: OpenApiResponse(description="Доступ запрещён"),
        },
        summary="Создание записи дневника",
        tags=["diagnoses"],
    ),
    partial_update=extend_schema(
        parameters=[
            OpenApiParameter(
                name="patient_id",
                type=int,
                location=OpenApiParameter.QUERY,
                description="ID пациента — обязателен для опекуна",
                required=False,
            ),
        ],
        request=DiaryEntryCreateSerializer,
        responses={
            200: DiaryEntryInfo,
            400: OpenApiResponse(description="Ошибка валидации"),
            403: OpenApiResponse(description="Доступ запрещён или запись принадлежит другому пациенту"),
            404: OpenApiResponse(description="Запись не найдена"),
        },
        summary="Обновление записи дневника",
        tags=["diagnoses"],
    ),
    destroy=extend_schema(
        parameters=[
            OpenApiParameter(
                name="patient_id",
                type=int,
                location=OpenApiParameter.QUERY,
                description="ID пациента — обязателен для опекуна",
                required=False,
            ),
        ],
        responses={
            204: OpenApiResponse(description="Запись удалена"),
            403: OpenApiResponse(description="Доступ запрещён или запись принадлежит другому пациенту"),
            404: OpenApiResponse(description="Запись не найдена"),
        },
        summary="Удаление записи дневника",
        tags=["diagnoses"],
    ),
)
class DiaryEntryViewSet(ViewSet):
    """CRUD-операции над записями дневника самонаблюдения пациента."""

    permission_classes: ClassVar = [IsAuthenticated]

    def list(self, request: Request) -> Response:
        """Возвращает все записи дневника пациента в обратном хронологическом порядке."""
        patient = _resolve_patient_for_diary(request, request.query_params.get("patient_id"))
        entries = DiaryEntry.objects.filter(patient=patient).select_related("author").prefetch_related("values__metric")
        return Response(DiaryEntryInfo(entries, many=True).data, status=status.HTTP_200_OK)

    def create(self, request: Request) -> Response:
        """Создаёт новую запись дневника с переданным набором значений метрик."""
        patient = _resolve_patient_for_diary(request, request.query_params.get("patient_id"))
        serializer = DiaryEntryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = DiaryEntry.objects.create(patient=patient, author=request.user)
        DiaryEntryValue.objects.bulk_create(
            [
                DiaryEntryValue(
                    entry=entry,
                    metric_id=v["metric_id"],
                    value_number=v.get("value_number"),
                    value_text=v.get("value_text", ""),
                    value_boolean=v.get("value_boolean"),
                )
                for v in serializer.validated_data["values"]
            ]
        )
        entry_with_values = (
            DiaryEntry.objects.select_related("author").prefetch_related("values__metric").get(pk=entry.pk)
        )
        return Response(DiaryEntryInfo(entry_with_values).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request: Request, pk: int | None = None) -> Response:
        """Заменяет значения метрик в существующей записи дневника через upsert."""
        patient = _resolve_patient_for_diary(request, request.query_params.get("patient_id"))
        entry = get_object_or_404(DiaryEntry, pk=pk, patient=patient)
        serializer = DiaryEntryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        for v in serializer.validated_data["values"]:
            DiaryEntryValue.objects.update_or_create(
                entry=entry,
                metric_id=v["metric_id"],
                defaults={
                    "value_number": v.get("value_number"),
                    "value_text": v.get("value_text", ""),
                    "value_boolean": v.get("value_boolean"),
                },
            )
        entry_with_values = (
            DiaryEntry.objects.select_related("author").prefetch_related("values__metric").get(pk=entry.pk)
        )
        return Response(DiaryEntryInfo(entry_with_values).data, status=status.HTTP_200_OK)

    def destroy(self, request: Request, pk: int | None = None) -> Response:
        """Удаляет запись дневника вместе со всеми её значениями метрик."""
        patient = _resolve_patient_for_diary(request, request.query_params.get("patient_id"))
        entry = get_object_or_404(DiaryEntry, pk=pk, patient=patient)
        entry.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
