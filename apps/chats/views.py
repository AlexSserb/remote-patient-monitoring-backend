"""Представления для получения списка чатов, групп чатов и работы с сообщениями."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from django.contrib.auth import get_user_model
from django.db.models import F, OuterRef, Subquery
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.chats.models import Chat, Message
from apps.chats.serializers import (
    CaregiverChatGroupSerializer,
    ChatItemSerializer,
    DoctorChatGroupSerializer,
    MessagePageSerializer,
    MessageSerializer,
)
from apps.chats.services import edit_message, get_messages_page
from apps.users.models import Role, User

if TYPE_CHECKING:
    from rest_framework.request import Request

UserModel = get_user_model()


def _annotate_last_message(qs: Any) -> Any:
    """Добавляет аннотации с данными последнего сообщения чата через подзапрос."""
    last_msg = Message.objects.filter(chat=OuterRef("pk")).order_by("-id")
    return qs.annotate(
        _lm_content=Subquery(last_msg.values("content")[:1]),
        _lm_sender_first=Subquery(last_msg.values("sender__first_name")[:1]),
        _lm_sender_last=Subquery(last_msg.values("sender__last_name")[:1]),
    )


def _last_message_dict(chat: Chat) -> dict | None:
    """Извлекает превью последнего сообщения из аннотаций объекта чата."""
    content = getattr(chat, "_lm_content", None)
    if not content:
        return None
    first = getattr(chat, "_lm_sender_first", "") or ""
    last = getattr(chat, "_lm_sender_last", "") or ""
    return {"content": content, "sender_name": f"{first} {last}".strip()}


def _build_chat_lookup(user: User) -> dict[tuple[frozenset, int | None], Chat]:
    """Строит словарь {(frozenset участников, patient_id)} → чат для всех чатов пользователя."""
    qs = _annotate_last_message(Chat.objects.filter(participants=user).prefetch_related("participants"))
    return {(frozenset(p.pk for p in chat.participants.all()), chat.patient_id): chat for chat in qs}


def _member_dict(user: User, chat: Chat | None) -> dict:
    """Возвращает словарь с данными участника и привязанного чата."""
    return {
        "id": user.pk,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "chat_id": chat.pk if chat else None,
        "last_message_at": chat.last_message_at if chat else None,
        "last_message": _last_message_dict(chat) if chat else None,
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

    chats = _annotate_last_message(
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
        403: OpenApiResponse(description="Доступ запрещён — только для докторов"),
    },
    summary="Группы чатов доктора",
    tags=["chats"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_doctor_chat_groups(request: Request) -> Response:
    """Возвращает группы чатов по пациентам — только для докторов."""
    user = cast("User", request.user)
    if user.role != Role.DOCTOR:
        raise PermissionDenied

    chat_lookup = _build_chat_lookup(user)
    return Response(_build_doctor_groups(user, chat_lookup), status=status.HTTP_200_OK)


@extend_schema(
    responses={
        200: CaregiverChatGroupSerializer(many=True),
        403: OpenApiResponse(description="Доступ запрещён — только для опекунов"),
    },
    summary="Группы чатов опекуна",
    tags=["chats"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_caregiver_chat_groups(request: Request) -> Response:
    """Возвращает группы чатов по пациентам — только для опекунов."""
    user = cast("User", request.user)
    if user.role != Role.CAREGIVER:
        raise PermissionDenied

    chat_lookup = _build_chat_lookup(user)
    return Response(_build_caregiver_groups(user, chat_lookup), status=status.HTTP_200_OK)


def _build_doctor_groups(user: User, chat_lookup: dict[tuple[frozenset, int | None], Chat]) -> list[dict]:
    """Формирует группы чатов для доктора: пациент + его опекуны."""
    patients = (
        UserModel.objects.filter(patient_doctors__doctor=user)
        .prefetch_related("patient_caregivers__caregiver")
        .order_by("last_name", "first_name")
    )
    groups = []
    for patient in patients:
        patient = cast("User", patient)
        patient_chat = chat_lookup.get((frozenset([user.pk, patient.pk]), patient.pk))
        caregivers = [
            _member_dict(
                cast("User", cp.caregiver),
                chat_lookup.get((frozenset([user.pk, cp.caregiver.pk]), patient.pk)),
            )
            for cp in patient.patient_caregivers.all()  # ty: ignore[unresolved-attribute]
        ]
        groups.append(
            DoctorChatGroupSerializer({"patient": _member_dict(patient, patient_chat), "caregivers": caregivers}).data
        )
    return groups


def _get_chat_for_participant(chat_id: int, user: User) -> Chat:
    """Возвращает чат по id, проверяя, что пользователь является его участником."""
    try:
        chat = Chat.objects.get(pk=chat_id)
    except Chat.DoesNotExist:
        raise NotFound from None
    if not chat.participants.filter(pk=user.pk).exists():
        raise PermissionDenied
    return chat


def _build_caregiver_groups(user: User, chat_lookup: dict[tuple[frozenset, int | None], Chat]) -> list[dict]:
    """Формирует группы чатов для опекуна: пациент + его доктора + другие опекуны."""
    patients = (
        UserModel.objects.filter(patient_caregivers__caregiver=user)
        .prefetch_related("patient_doctors__doctor", "patient_caregivers__caregiver")
        .order_by("last_name", "first_name")
    )
    groups = []
    for patient in patients:
        patient = cast("User", patient)
        patient_chat = chat_lookup.get((frozenset([user.pk, patient.pk]), patient.pk))
        doctors = [
            _member_dict(dp.doctor, chat_lookup.get((frozenset([user.pk, dp.doctor.pk]), patient.pk)))
            for dp in patient.patient_doctors.all()  # ty: ignore[unresolved-attribute]
        ]
        caregivers = [
            _member_dict(cp.caregiver, chat_lookup.get((frozenset([user.pk, cp.caregiver.pk]), patient.pk)))
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


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="before_id",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Загрузить сообщения старее указанного id (для скроллинга вверх)",
        )
    ],
    responses={
        200: MessagePageSerializer,
        403: OpenApiResponse(description="Пользователь не является участником чата"),
        404: OpenApiResponse(description="Чат не найден"),
    },
    summary="Список сообщений чата",
    tags=["chats"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_messages(request: Request, chat_id: int) -> Response:
    """Возвращает страницу из 100 сообщений чата в порядке убывания id."""
    user = cast("User", request.user)
    chat = _get_chat_for_participant(chat_id, user)

    before_id: int | None = None
    raw = request.query_params.get("before_id")
    if raw is not None:
        try:
            before_id = int(raw)
        except ValueError:
            raise ValidationError({"before_id": "Должно быть целым числом."}) from None

    messages, has_more = get_messages_page(chat, before_id)
    serializer = MessagePageSerializer({"results": messages, "has_more": has_more})
    return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(
    responses={
        204: OpenApiResponse(description="Сообщение удалено"),
        403: OpenApiResponse(description="Нельзя удалить чужое сообщение или нет доступа к чату"),
        404: OpenApiResponse(description="Сообщение не найдено"),
    },
    summary="Удаление сообщения",
    tags=["chats"],
)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_message(request: Request, chat_id: int, message_id: int) -> Response:
    """Помечает сообщение удалённым — только отправитель может удалить своё сообщение."""
    user = cast("User", request.user)
    _get_chat_for_participant(chat_id, user)

    try:
        message = Message.objects.get(pk=message_id, chat_id=chat_id)
    except Message.DoesNotExist:
        raise NotFound from None

    if message.sender_id != user.pk:  # ty: ignore[unresolved-attribute]
        raise PermissionDenied

    Message.objects.filter(pk=message_id).update(is_deleted=True)
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {"content": {"type": "string"}},
            "required": ["content"],
        }
    },
    responses={
        200: MessagePageSerializer,
        403: OpenApiResponse(description="Нельзя редактировать чужое сообщение или нет доступа к чату"),
        404: OpenApiResponse(description="Сообщение не найдено или удалено"),
    },
    summary="Редактирование сообщения",
    tags=["chats"],
)
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def edit_message_view(request: Request, chat_id: int, message_id: int) -> Response:
    """Обновляет текст сообщения — только отправитель может редактировать своё сообщение."""
    user = cast("User", request.user)
    chat = _get_chat_for_participant(chat_id, user)

    content: str = (request.data.get("content") or "").strip()
    if not content:
        raise ValidationError({"content": "Текст сообщения не может быть пустым."})

    updated = edit_message(message_id, chat, user.pk, content)
    if not updated:
        raise NotFound

    message = Message.objects.select_related("sender").get(pk=message_id)
    return Response(MessageSerializer(message).data)
