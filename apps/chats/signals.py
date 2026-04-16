"""Сигналы для автоматического создания чатов при установке связей между пользователями."""

from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.chats.services import get_or_create_direct_chat
from apps.users.models import CaregiverPatient, DoctorPatient

logger = logging.getLogger(__name__)


def _log_chat(chat: object, user_a_id: int, user_b_id: int, *, is_new: bool) -> None:
    """Выводит отладочное сообщение о результате создания или поиска чата."""
    action = "Created" if is_new else "Found existing"
    logger.debug("%s chat %s between users %d and %d", action, getattr(chat, "pk", "?"), user_a_id, user_b_id)


@receiver(post_save, sender=DoctorPatient)
def create_chats_for_doctor_patient(
    sender: type[DoctorPatient],  # noqa: ARG001
    instance: DoctorPatient,
    created: bool,  # noqa: FBT001
    **_kwargs: object,
) -> None:
    """Создаёт чаты доктора с пациентом и всеми опекунами этого пациента."""
    if not created:
        return

    doctor = instance.doctor
    patient = instance.patient

    chat, is_new = get_or_create_direct_chat(doctor, patient)
    _log_chat(chat, doctor.pk, patient.pk, is_new=is_new)

    for cp in CaregiverPatient.objects.filter(patient=patient).select_related("caregiver"):
        chat, is_new = get_or_create_direct_chat(doctor, cp.caregiver)
        _log_chat(chat, doctor.pk, cp.caregiver.pk, is_new=is_new)


@receiver(post_save, sender=CaregiverPatient)
def create_chats_for_caregiver_patient(
    sender: type[CaregiverPatient],  # noqa: ARG001
    instance: CaregiverPatient,
    created: bool,  # noqa: FBT001
    **_kwargs: object,
) -> None:
    """Создаёт чаты опекуна с пациентом, его докторами и другими опекунами."""
    if not created:
        return

    caregiver = instance.caregiver
    patient = instance.patient

    chat, is_new = get_or_create_direct_chat(caregiver, patient)
    _log_chat(chat, caregiver.pk, patient.pk, is_new=is_new)

    for dp in DoctorPatient.objects.filter(patient=patient).select_related("doctor"):
        chat, is_new = get_or_create_direct_chat(caregiver, dp.doctor)
        _log_chat(chat, caregiver.pk, dp.doctor.pk, is_new=is_new)

    other_cps = (
        CaregiverPatient.objects.filter(patient=patient).exclude(caregiver=caregiver).select_related("caregiver")
    )
    for cp in other_cps:
        chat, is_new = get_or_create_direct_chat(caregiver, cp.caregiver)
        _log_chat(chat, caregiver.pk, cp.caregiver.pk, is_new=is_new)
