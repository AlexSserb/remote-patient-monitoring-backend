"""Представления для получения списка чатов и групп чатов."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from django.contrib.auth import get_user_model
from django.db.models import F
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.chats.models import Chat
from apps.chats.serializers import (
    CaregiverChatGroupSerializer,
    ChatItemSerializer,
    DoctorChatGroupSerializer,
)
from apps.users.models import Role, User

if TYPE_CHECKING:
    from rest_framework.request import Request

UserModel = get_user_model()


def _build_chat_lookup(user: User) -> dict[frozenset, Chat]:
    """Строит словарь {frozenset участников} → чат для всех чатов пользователя."""
    chats = Chat.objects.filter(participants=user).prefetch_related("participants")
    return {frozenset(p.pk for p in chat.participants.all()): chat for chat in chats}


def _member_dict(user: User, chat: Chat | None) -> dict:
    """Возвращает словарь с данными участника и привязанного чата."""
    return {
        "id": user.pk,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "chat_id": chat.pk if chat else None,
        "last_message_at": chat.last_message_at if chat else None,
    }


@extend_schema(
    responses={
        200: ChatItemSerializer(many=True),
        403: OpenApiResponse(description="Доступ запрещён — только для пациентов"),
    },
    summary="Список чатов пациента",
    tags=["chats"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_chats(request: Request) -> Response:
    """Возвращает плоский список чатов — только для пациентов."""
    user = cast("User", request.user)
    if user.role != Role.PATIENT:
        raise PermissionDenied

    chats = (
        Chat.objects.filter(participants=user)
        .prefetch_related("participants")
        # чаты без сообщений опускаем в конец
        .order_by(F("last_message_at").desc(nulls_last=True), "-created_at")
    )
    serializer = ChatItemSerializer(chats, many=True, context={"request": request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(
    responses={
        200: DoctorChatGroupSerializer(many=True),
        403: OpenApiResponse(description="Доступ запрещён — только для докторов и опекунов"),
    },
    summary="Группы чатов доктора или опекуна",
    tags=["chats"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_chat_groups(request: Request) -> Response:
    """Возвращает группы чатов по пациентам — только для докторов и опекунов."""
    user = cast("User", request.user)
    if user.role not in (Role.DOCTOR, Role.CAREGIVER):
        raise PermissionDenied

    # Один запрос на все чаты текущего пользователя для O(1)-поиска по паре
    chat_lookup = _build_chat_lookup(user)

    if user.role == Role.DOCTOR:
        return Response(_build_doctor_groups(user, chat_lookup), status=status.HTTP_200_OK)
    return Response(_build_caregiver_groups(user, chat_lookup), status=status.HTTP_200_OK)


def _build_doctor_groups(user: User, chat_lookup: dict[frozenset, Chat]) -> list[dict]:
    """Формирует группы чатов для доктора: пациент + его опекуны."""
    patients = (
        UserModel.objects.filter(patient_doctors__doctor=user)
        .prefetch_related("patient_caregivers__caregiver")
        .order_by("last_name", "first_name")
    )
    groups = []
    for patient in patients:
        patient = cast("User", patient)
        patient_chat = chat_lookup.get(frozenset([user.pk, patient.pk]))
        caregivers = [
            _member_dict(cast("User", cp.caregiver), chat_lookup.get(frozenset([user.pk, cp.caregiver.pk])))
            for cp in patient.patient_caregivers.all()  # ty: ignore[unresolved-attribute]
        ]
        groups.append(
            DoctorChatGroupSerializer({"patient": _member_dict(patient, patient_chat), "caregivers": caregivers}).data
        )
    return groups


def _build_caregiver_groups(user: User, chat_lookup: dict[frozenset, Chat]) -> list[dict]:
    """Формирует группы чатов для опекуна: пациент + его доктора + другие опекуны."""
    patients = (
        UserModel.objects.filter(patient_caregivers__caregiver=user)
        .prefetch_related("patient_doctors__doctor", "patient_caregivers__caregiver")
        .order_by("last_name", "first_name")
    )
    groups = []
    for patient in patients:
        patient = cast("User", patient)
        patient_chat = chat_lookup.get(frozenset([user.pk, patient.pk]))
        doctors = [
            _member_dict(cast("User", dp.doctor), chat_lookup.get(frozenset([user.pk, dp.doctor.pk])))
            for dp in patient.patient_doctors.all()  # ty: ignore[unresolved-attribute]
        ]
        caregivers = [
            _member_dict(cast("User", cp.caregiver), chat_lookup.get(frozenset([user.pk, cp.caregiver.pk])))
            for cp in patient.patient_caregivers.all()  # ty: ignore[unresolved-attribute]
            if cp.caregiver.pk != user.pk  # исключаем себя
        ]
        groups.append(
            CaregiverChatGroupSerializer(
                {
                    "patient": _member_dict(patient, patient_chat),
                    "doctors": doctors,
                    "caregivers": caregivers,
                }
            ).data
        )
    return groups
