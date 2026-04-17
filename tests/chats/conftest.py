"""Фикстуры для тестов чатов."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.users.models import CaregiverPatient, DoctorPatient, Role, User
from apps.users.services import issue_token_pair


@pytest.fixture
def doctor(db: None) -> User:
    """Создаёт тестового доктора."""
    return User.objects.create_user(
        email="doctor@example.com",
        password="Pass123!",
        first_name="Иван",
        last_name="Докторов",
        role=Role.DOCTOR,
    )


@pytest.fixture
def doctor2(db: None) -> User:
    """Создаёт второго тестового доктора."""
    return User.objects.create_user(
        email="doctor2@example.com",
        password="Pass123!",
        first_name="Пётр",
        last_name="Лечебный",
        role=Role.DOCTOR,
    )


@pytest.fixture
def patient(db: None) -> User:
    """Создаёт тестового пациента."""
    return User.objects.create_user(
        email="patient@example.com",
        password="Pass123!",
        first_name="Мария",
        last_name="Пациентова",
        role=Role.PATIENT,
    )


@pytest.fixture
def patient2(db: None) -> User:
    """Создаёт второго тестового пациента без связей."""
    return User.objects.create_user(
        email="patient2@example.com",
        password="Pass123!",
        first_name="Алексей",
        last_name="Новиков",
        role=Role.PATIENT,
    )


@pytest.fixture
def caregiver(db: None) -> User:
    """Создаёт тестового опекуна."""
    return User.objects.create_user(
        email="caregiver@example.com",
        password="Pass123!",
        first_name="Надежда",
        last_name="Орлова",
        role=Role.CAREGIVER,
    )


@pytest.fixture
def caregiver2(db: None) -> User:
    """Создаёт второго тестового опекуна."""
    return User.objects.create_user(
        email="caregiver2@example.com",
        password="Pass123!",
        first_name="Андрей",
        last_name="Беляев",
        role=Role.CAREGIVER,
    )


def make_auth_client(user: User) -> APIClient:
    """Возвращает аутентифицированный APIClient для указанного пользователя."""
    client = APIClient()
    tokens = issue_token_pair(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


@pytest.fixture
def doctor_client(doctor: User) -> APIClient:
    """Возвращает API-клиент, аутентифицированный как доктор."""
    return make_auth_client(doctor)


@pytest.fixture
def patient_client(patient: User) -> APIClient:
    """Возвращает API-клиент, аутентифицированный как пациент."""
    return make_auth_client(patient)


@pytest.fixture
def caregiver_client(caregiver: User) -> APIClient:
    """Возвращает API-клиент, аутентифицированный как опекун."""
    return make_auth_client(caregiver)


@pytest.fixture
def doctor_patient_link(doctor: User, patient: User) -> DoctorPatient:
    """Создаёт связь доктор-пациент (сигнал автоматически создаёт чат)."""
    return DoctorPatient.objects.create(doctor=doctor, patient=patient)


@pytest.fixture
def caregiver_patient_link(caregiver: User, patient: User) -> CaregiverPatient:
    """Создаёт связь опекун-пациент (сигнал автоматически создаёт чат)."""
    return CaregiverPatient.objects.create(caregiver=caregiver, patient=patient)
