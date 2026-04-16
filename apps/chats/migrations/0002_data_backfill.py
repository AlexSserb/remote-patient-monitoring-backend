"""Дата-миграция: создание чатов для всех существующих связей доктор-пациент и опекун-пациент."""

from __future__ import annotations

from django.db import migrations


def _get_or_create_direct_chat(Chat: object, user_a: object, user_b: object) -> None:
    """Создаёт чат между двумя пользователями, если он ещё не существует."""
    from django.db.models import Count

    existing = (
        Chat.objects.filter(participants=user_a)
        .filter(participants=user_b)
        .annotate(n=Count("participants"))
        .filter(n=2)
        .first()
    )
    if existing:
        return
    chat = Chat.objects.create()
    chat.participants.add(user_a, user_b)


def create_chats(apps: object, schema_editor: object) -> None:
    """Создаёт чаты для всех существующих связей доктор-пациент и опекун-пациент."""
    Chat = apps.get_model("chats", "Chat")
    DoctorPatient = apps.get_model("users", "DoctorPatient")
    CaregiverPatient = apps.get_model("users", "CaregiverPatient")

    # Чаты доктор ↔ пациент и доктор ↔ опекуны пациента
    for dp in DoctorPatient.objects.select_related("doctor", "patient"):
        _get_or_create_direct_chat(Chat, dp.doctor, dp.patient)
        for cp in CaregiverPatient.objects.filter(patient=dp.patient).select_related("caregiver"):
            _get_or_create_direct_chat(Chat, dp.doctor, cp.caregiver)

    # Чаты опекун ↔ пациент, опекун ↔ доктора и опекун ↔ другие опекуны
    for cp in CaregiverPatient.objects.select_related("caregiver", "patient"):
        _get_or_create_direct_chat(Chat, cp.caregiver, cp.patient)
        for dp in DoctorPatient.objects.filter(patient=cp.patient).select_related("doctor"):
            _get_or_create_direct_chat(Chat, cp.caregiver, dp.doctor)
        for other_cp in (
            CaregiverPatient.objects.filter(patient=cp.patient)
            .exclude(caregiver=cp.caregiver)
            .select_related("caregiver")
        ):
            _get_or_create_direct_chat(Chat, cp.caregiver, other_cp.caregiver)


def delete_chats(apps: object, schema_editor: object) -> None:
    """Удаляет все чаты (откат миграции)."""
    Chat = apps.get_model("chats", "Chat")
    Chat.objects.all().delete()


class Migration(migrations.Migration):
    """Дата-миграция для создания чатов по существующим связям."""

    dependencies = [
        ("chats", "0001_initial"),
        ("users", "0002_add_doctor_patient_caregiver_patient"),
    ]

    operations = [
        migrations.RunPython(create_chats, reverse_code=delete_chats),
    ]
