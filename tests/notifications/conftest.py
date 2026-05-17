"""Фикстуры для тестов системы уведомлений."""

from __future__ import annotations

from datetime import time

import pytest

from apps.notifications.models import NotificationSchedule
from apps.users.models import CaregiverPatient, DoctorPatient, Role, User


@pytest.fixture
def doctor(db: None) -> User:
    """Создаёт пользователя с ролью доктора."""
    return User.objects.create_user(
        email="doctor@example.com",
        password="pass",
        first_name="Иван",
        last_name="Докторов",
        role=Role.DOCTOR,
    )


@pytest.fixture
def patient(db: None) -> User:
    """Создаёт пользователя с ролью пациента."""
    return User.objects.create_user(
        email="patient@example.com",
        password="pass",
        first_name="Пётр",
        last_name="Пациентов",
        role=Role.PATIENT,
    )


@pytest.fixture
def caregiver(db: None) -> User:
    """Создаёт пользователя с ролью опекуна."""
    return User.objects.create_user(
        email="caregiver@example.com",
        password="pass",
        first_name="Анна",
        last_name="Опекунова",
        role=Role.CAREGIVER,
    )


@pytest.fixture
def other_patient(db: None) -> User:
    """Создаёт второго пациента для проверки изоляции доступа."""
    return User.objects.create_user(
        email="other_patient@example.com",
        password="pass",
        first_name="Сидор",
        last_name="Другов",
        role=Role.PATIENT,
    )


@pytest.fixture
def doctor_patient(doctor: User, patient: User) -> DoctorPatient:
    """Создаёт связь доктор-пациент между фикстурными пользователями."""
    return DoctorPatient.objects.create(doctor=doctor, patient=patient)


@pytest.fixture
def caregiver_patient(caregiver: User, patient: User) -> CaregiverPatient:
    """Создаёт связь опекун-пациент между фикстурными пользователями."""
    return CaregiverPatient.objects.create(caregiver=caregiver, patient=patient)


@pytest.fixture
def schedule(patient: User) -> NotificationSchedule:
    """Создаёт расписание уведомлений для пациента на себя."""
    return NotificationSchedule.objects.create(
        recipient=patient,
        patient=patient,
        days_of_week=[0, 1, 2],
        times=[time(9, 0), time(21, 0)],
        is_enabled=True,
    )
