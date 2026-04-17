"""Тесты API-эндпоинтов списка чатов и групп чатов."""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.chats.models import Chat
from apps.chats.services import get_or_create_direct_chat
from apps.users.models import CaregiverPatient, DoctorPatient, Role, User

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Плоский список чатов (GET /api/chats/) — только пациент
# ---------------------------------------------------------------------------


class TestListChats:
    """Тесты эндпоинта GET /api/chats/ для пациентов."""

    URL = "chats-list"

    def test_unauthenticated_returns_401(self, api_client: APIClient) -> None:
        """Неаутентифицированный запрос возвращает 401."""
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_doctor_returns_403(self, doctor_client: APIClient) -> None:
        """Доктор получает 403 при обращении к плоскому списку."""
        response = doctor_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_caregiver_returns_403(self, caregiver_client: APIClient) -> None:
        """Опекун получает 403 при обращении к плоскому списку."""
        response = caregiver_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_patient_with_no_connections_returns_empty_list(self, patient_client: APIClient) -> None:
        """Пациент без связей получает пустой список чатов."""
        response = patient_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_patient_sees_chat_with_doctor(self, patient_client: APIClient, doctor: User, patient: User) -> None:
        """Пациент видит чат с доктором после создания связи."""
        DoctorPatient.objects.create(doctor=doctor, patient=patient)
        response = patient_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        interlocutor = response.data[0]["interlocutor"]
        assert interlocutor["id"] == doctor.pk
        assert interlocutor["role"] == Role.DOCTOR

    def test_patient_sees_chat_with_caregiver(self, patient_client: APIClient, caregiver: User, patient: User) -> None:
        """Пациент видит чат с опекуном после создания связи."""
        CaregiverPatient.objects.create(caregiver=caregiver, patient=patient)
        response = patient_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        interlocutor = response.data[0]["interlocutor"]
        assert interlocutor["id"] == caregiver.pk
        assert interlocutor["role"] == Role.CAREGIVER

    def test_patient_sees_all_connected_chats(
        self,
        patient_client: APIClient,
        doctor: User,
        doctor2: User,
        caregiver: User,
        patient: User,
    ) -> None:
        """Пациент видит чаты со всеми подключёнными докторами и опекунами."""
        DoctorPatient.objects.create(doctor=doctor, patient=patient)
        DoctorPatient.objects.create(doctor=doctor2, patient=patient)
        CaregiverPatient.objects.create(caregiver=caregiver, patient=patient)
        response = patient_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_200_OK
        # 2 доктора + 1 опекун = 3 чата
        assert len(response.data) == 3

    def test_chat_contains_required_fields(self, patient_client: APIClient, doctor: User, patient: User) -> None:
        """Каждый элемент списка содержит обязательные поля."""
        DoctorPatient.objects.create(doctor=doctor, patient=patient)
        response = patient_client.get(reverse(self.URL))
        item = response.data[0]
        assert "id" in item
        assert "interlocutor" in item
        assert "last_message_at" in item
        assert "created_at" in item


# ---------------------------------------------------------------------------
# Группы чатов доктора (GET /api/chats/doctor-groups/)
# ---------------------------------------------------------------------------


class TestListDoctorChatGroups:
    """Тесты эндпоинта GET /api/chats/doctor-groups/ для докторов."""

    URL = "chats-doctor-groups"

    def test_unauthenticated_returns_401(self, api_client: APIClient) -> None:
        """Неаутентифицированный запрос возвращает 401."""
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_patient_returns_403(self, patient_client: APIClient) -> None:
        """Пациент получает 403 при обращении к группам доктора."""
        response = patient_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_doctor_with_no_patients_returns_empty_list(self, doctor_client: APIClient) -> None:
        """Доктор без пациентов получает пустой список групп."""
        response = doctor_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_doctor_sees_group_per_patient(
        self, doctor_client: APIClient, doctor: User, patient: User, patient2: User
    ) -> None:
        """Доктор получает одну группу на каждого прикреплённого пациента."""
        DoctorPatient.objects.create(doctor=doctor, patient=patient)
        DoctorPatient.objects.create(doctor=doctor, patient=patient2)
        response = doctor_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_doctor_group_contains_patient_and_caregivers(
        self,
        doctor_client: APIClient,
        doctor: User,
        patient: User,
        caregiver: User,
    ) -> None:
        """Группа доктора содержит пациента и его опекуна."""
        DoctorPatient.objects.create(doctor=doctor, patient=patient)
        CaregiverPatient.objects.create(caregiver=caregiver, patient=patient)
        response = doctor_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_200_OK
        group = response.data[0]
        assert group["patient"]["id"] == patient.pk
        assert len(group["caregivers"]) == 1
        assert group["caregivers"][0]["id"] == caregiver.pk

    def test_doctor_group_has_chat_ids(
        self, doctor_client: APIClient, doctor: User, patient: User, caregiver: User
    ) -> None:
        """Поля patient и caregivers содержат непустой chat_id."""
        DoctorPatient.objects.create(doctor=doctor, patient=patient)
        CaregiverPatient.objects.create(caregiver=caregiver, patient=patient)
        response = doctor_client.get(reverse(self.URL))
        group = response.data[0]
        assert group["patient"]["chat_id"] is not None
        assert group["caregivers"][0]["chat_id"] is not None

    def test_doctor_sees_empty_group_when_patient_has_no_caregivers(
        self, doctor_client: APIClient, doctor: User, patient: User
    ) -> None:
        """Группа доктора содержит пустой список опекунов, если их нет у пациента."""
        DoctorPatient.objects.create(doctor=doctor, patient=patient)
        response = doctor_client.get(reverse(self.URL))
        group = response.data[0]
        assert group["caregivers"] == []

    def test_doctor_group_member_fields(self, doctor_client: APIClient, doctor: User, patient: User) -> None:
        """Участник группы содержит обязательные поля."""
        DoctorPatient.objects.create(doctor=doctor, patient=patient)
        response = doctor_client.get(reverse(self.URL))
        member = response.data[0]["patient"]
        assert "id" in member
        assert "first_name" in member
        assert "last_name" in member
        assert "chat_id" in member
        assert "last_message_at" in member

    def test_no_duplicate_chats_on_repeated_signal(self, doctor: User, patient: User) -> None:
        """Повторный вызов сервиса создания чата не создаёт дубликата."""
        DoctorPatient.objects.create(doctor=doctor, patient=patient)
        # Сигнал уже создал чат; вызываем сервис напрямую
        get_or_create_direct_chat(doctor, patient, patient)
        assert Chat.objects.filter(participants=doctor).filter(participants=patient).count() == 1


# ---------------------------------------------------------------------------
# Группы чатов опекуна (GET /api/chats/caregiver-groups/)
# ---------------------------------------------------------------------------


class TestListCaregiverChatGroups:
    """Тесты эндпоинта GET /api/chats/caregiver-groups/ для опекунов."""

    URL = "chats-caregiver-groups"

    def test_unauthenticated_returns_401(self, api_client: APIClient) -> None:
        """Неаутентифицированный запрос возвращает 401."""
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_patient_returns_403(self, patient_client: APIClient) -> None:
        """Пациент получает 403 при обращении к группам опекуна."""
        response = patient_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_caregiver_with_no_patients_returns_empty_list(self, caregiver_client: APIClient) -> None:
        """Опекун без пациентов получает пустой список групп."""
        response = caregiver_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_caregiver_sees_group_per_patient(
        self, caregiver_client: APIClient, caregiver: User, patient: User, patient2: User
    ) -> None:
        """Опекун получает одну группу на каждого прикреплённого пациента."""
        CaregiverPatient.objects.create(caregiver=caregiver, patient=patient)
        CaregiverPatient.objects.create(caregiver=caregiver, patient=patient2)
        response = caregiver_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_caregiver_group_contains_patient_doctors_and_other_caregivers(
        self,
        caregiver_client: APIClient,
        caregiver: User,
        caregiver2: User,
        doctor: User,
        patient: User,
    ) -> None:
        """Группа опекуна содержит пациента, его докторов и других опекунов."""
        DoctorPatient.objects.create(doctor=doctor, patient=patient)
        CaregiverPatient.objects.create(caregiver=caregiver, patient=patient)
        CaregiverPatient.objects.create(caregiver=caregiver2, patient=patient)
        response = caregiver_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_200_OK
        group = response.data[0]
        assert group["patient"]["id"] == patient.pk
        assert len(group["doctors"]) == 1
        assert group["doctors"][0]["id"] == doctor.pk
        assert len(group["caregivers"]) == 1
        assert group["caregivers"][0]["id"] == caregiver2.pk

    def test_caregiver_not_in_own_group(
        self,
        caregiver_client: APIClient,
        caregiver: User,
        caregiver2: User,
        patient: User,
    ) -> None:
        """Текущий опекун не отображается в списке опекунов своей группы."""
        CaregiverPatient.objects.create(caregiver=caregiver, patient=patient)
        CaregiverPatient.objects.create(caregiver=caregiver2, patient=patient)
        response = caregiver_client.get(reverse(self.URL))
        caregiver_ids = [c["id"] for c in response.data[0]["caregivers"]]
        assert caregiver.pk not in caregiver_ids

    def test_caregiver_group_has_chat_ids(
        self,
        caregiver_client: APIClient,
        caregiver: User,
        caregiver2: User,
        doctor: User,
        patient: User,
    ) -> None:
        """Поля patient, doctors и caregivers содержат непустые chat_id."""
        DoctorPatient.objects.create(doctor=doctor, patient=patient)
        CaregiverPatient.objects.create(caregiver=caregiver, patient=patient)
        CaregiverPatient.objects.create(caregiver=caregiver2, patient=patient)
        response = caregiver_client.get(reverse(self.URL))
        group = response.data[0]
        assert group["patient"]["chat_id"] is not None
        assert group["doctors"][0]["chat_id"] is not None
        assert group["caregivers"][0]["chat_id"] is not None

    def test_caregiver_group_structure_fields(
        self, caregiver_client: APIClient, caregiver: User, patient: User
    ) -> None:
        """Группа опекуна содержит обязательные ключи верхнего уровня."""
        CaregiverPatient.objects.create(caregiver=caregiver, patient=patient)
        response = caregiver_client.get(reverse(self.URL))
        group = response.data[0]
        assert "patient" in group
        assert "doctors" in group
        assert "caregivers" in group
