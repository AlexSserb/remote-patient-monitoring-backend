"""Представления приложения diagnoses."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from apps.diagnoses.serializers import (
    AnalyticsDataPointSerializer,
    AnalyticsMetricSerializer,
    AnalyticsQuerySerializer,
    AnalyticsResponseSerializer,
    DiagnosisShortSerializer,
    DiaryEntryCreateSerializer,
    DiaryEntryInfo,
    DiaryFieldSerializer,
)
from apps.diagnoses.services import DiagnosisService
from config.permissions import IsDoctorOrCaregiver

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
@permission_classes([IsAuthenticated, IsDoctorOrCaregiver])
def list_diagnoses(request: Request) -> Response:
    """Возвращает все диагнозы системы для использования в фильтрах."""
    diagnoses = DiagnosisService().list_diagnoses()
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
    fields = DiagnosisService().get_diary_fields(request.user, request.query_params.get("patient_id"))
    return Response(DiaryFieldSerializer(fields, many=True).data, status=status.HTTP_200_OK)


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
        entries = DiagnosisService().list_diary_entries(request.user, request.query_params.get("patient_id"))
        return Response(DiaryEntryInfo(entries, many=True).data, status=status.HTTP_200_OK)

    def create(self, request: Request) -> Response:
        """Создаёт новую запись дневника с переданным набором значений метрик."""
        serializer = DiaryEntryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = DiagnosisService().create_diary_entry(
            request.user, request.query_params.get("patient_id"), serializer.validated_data
        )
        return Response(DiaryEntryInfo(entry).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request: Request, pk: int | None = None) -> Response:
        """Заменяет значения метрик в существующей записи дневника через upsert."""
        serializer = DiaryEntryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = DiagnosisService().update_diary_entry(
            request.user, request.query_params.get("patient_id"), pk, serializer.validated_data
        )
        return Response(DiaryEntryInfo(entry).data, status=status.HTTP_200_OK)

    def destroy(self, request: Request, pk: int | None = None) -> Response:
        """Удаляет запись дневника вместе со всеми её значениями метрик."""
        DiagnosisService().delete_diary_entry(request.user, request.query_params.get("patient_id"), pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="patient_id",
            type=int,
            location=OpenApiParameter.QUERY,
            description="ID пациента — обязателен для доктора и опекуна, игнорируется для пациента",
            required=False,
        ),
        OpenApiParameter(
            name="date_from",
            type=str,
            location=OpenApiParameter.QUERY,
            description="Начало диапазона дат (YYYY-MM-DD). По умолчанию — 7 дней назад",
            required=False,
        ),
        OpenApiParameter(
            name="date_to",
            type=str,
            location=OpenApiParameter.QUERY,
            description="Конец диапазона дат (YYYY-MM-DD). По умолчанию — сегодня",
            required=False,
        ),
        OpenApiParameter(
            name="metric_ids",
            type=str,
            location=OpenApiParameter.QUERY,
            description="Через запятую ID метрик для отображения на графике",
            required=False,
        ),
    ],
    responses={
        200: AnalyticsResponseSerializer,
        400: OpenApiResponse(description="Неверный формат параметров"),
        403: OpenApiResponse(description="Доступ запрещён"),
        404: OpenApiResponse(description="Пациент не найден"),
    },
    summary="Аналитика дневниковых метрик пациента",
    tags=["diagnoses"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_analytics(request: Request) -> Response:
    """Возвращает числовые метрики пациента и точки данных за выбранный период."""
    serializer = AnalyticsQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    available_metrics, data_points = DiagnosisService().get_analytics(request.user, **serializer.validated_data)
    return Response(
        {
            "available_metrics": AnalyticsMetricSerializer(available_metrics, many=True).data,
            "data_points": AnalyticsDataPointSerializer(data_points, many=True).data,
        },
        status=status.HTTP_200_OK,
    )
