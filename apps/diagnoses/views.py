"""Представления приложения diagnoses."""

from __future__ import annotations

from typing import TYPE_CHECKING

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.diagnoses.models import Diagnosis
from apps.diagnoses.serializers import DiagnosisShortSerializer
from apps.users.models import Role

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
