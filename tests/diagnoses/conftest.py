"""Фикстуры для тестов модуля diagnoses."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.diagnoses.models import (
    Diagnosis,
    DiagnosisMetric,
    DiaryEntry,
    DiaryEntryValue,
    Metric,
    MetricType,
    PatientDiagnosis,
)
from apps.users.models import CaregiverPatient, Role, User
from apps.users.services import issue_token_pair

# ---------------------------------------------------------------------------
# Пользователи
# ---------------------------------------------------------------------------


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
    """Создаёт второго тестового пациента для проверки изоляции данных."""
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


# ---------------------------------------------------------------------------
# Аутентифицированные клиенты
# ---------------------------------------------------------------------------


def _make_auth_client(user: User) -> APIClient:
    """Возвращает APIClient с JWT-токеном для указанного пользователя."""
    client = APIClient()
    tokens = issue_token_pair(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


@pytest.fixture
def doctor_client(doctor: User) -> APIClient:
    """Возвращает API-клиент, аутентифицированный как доктор."""
    return _make_auth_client(doctor)


@pytest.fixture
def patient_client(patient: User) -> APIClient:
    """Возвращает API-клиент, аутентифицированный как пациент."""
    return _make_auth_client(patient)


@pytest.fixture
def patient2_client(patient2: User) -> APIClient:
    """Возвращает API-клиент, аутентифицированный как второй пациент."""
    return _make_auth_client(patient2)


@pytest.fixture
def caregiver_client(caregiver: User) -> APIClient:
    """Возвращает API-клиент, аутентифицированный как опекун."""
    return _make_auth_client(caregiver)


# ---------------------------------------------------------------------------
# Диагнозы и метрики
# ---------------------------------------------------------------------------


@pytest.fixture
def diagnosis(db: None) -> Diagnosis:
    """Создаёт тестовый диагноз сахарного диабета второго типа."""
    return Diagnosis.objects.create(name="Сахарный диабет II типа", code="E11", description="Тестовый диагноз")


@pytest.fixture
def metric_number(db: None) -> Metric:
    """Создаёт числовую метрику уровня глюкозы."""
    return Metric.objects.create(name="Глюкоза", code="glucose", unit="ммоль/л", type=MetricType.NUMBER)


@pytest.fixture
def metric_boolean(db: None) -> Metric:
    """Создаёт булеву метрику приёма инсулина."""
    return Metric.objects.create(name="Приём инсулина", code="insulin_taken", unit="", type=MetricType.BOOLEAN)


@pytest.fixture
def metric_text(db: None) -> Metric:
    """Создаёт текстовую метрику для заметок."""
    return Metric.objects.create(name="Заметки", code="notes", unit="", type=MetricType.TEXT)


@pytest.fixture
def dm_number(diagnosis: Diagnosis, metric_number: Metric) -> DiagnosisMetric:
    """Привязывает числовую метрику к диагнозу как обязательную с границами 3.9–10.0."""
    return DiagnosisMetric.objects.create(
        diagnosis=diagnosis,
        metric=metric_number,
        is_required=True,
        min_value=3.9,
        max_value=10.0,
    )


@pytest.fixture
def dm_boolean(diagnosis: Diagnosis, metric_boolean: Metric) -> DiagnosisMetric:
    """Привязывает булеву метрику к диагнозу как необязательную."""
    return DiagnosisMetric.objects.create(
        diagnosis=diagnosis,
        metric=metric_boolean,
        is_required=False,
    )


@pytest.fixture
def dm_text(diagnosis: Diagnosis, metric_text: Metric) -> DiagnosisMetric:
    """Привязывает текстовую метрику к диагнозу как необязательную."""
    return DiagnosisMetric.objects.create(
        diagnosis=diagnosis,
        metric=metric_text,
        is_required=False,
    )


@pytest.fixture
def patient_diagnosis(patient: User, diagnosis: Diagnosis, doctor: User) -> PatientDiagnosis:
    """Назначает тестовый диагноз пациенту от имени доктора."""
    return PatientDiagnosis.objects.create(patient=patient, diagnosis=diagnosis, assigned_by=doctor)


@pytest.fixture
def caregiver_patient_link(caregiver: User, patient: User) -> CaregiverPatient:
    """Создаёт связь опекун–пациент."""
    return CaregiverPatient.objects.create(caregiver=caregiver, patient=patient)


# ---------------------------------------------------------------------------
# Записи дневника
# ---------------------------------------------------------------------------


@pytest.fixture
def diary_entry(patient: User) -> DiaryEntry:
    """Создаёт пустую запись дневника для тестового пациента."""
    return DiaryEntry.objects.create(patient=patient)


@pytest.fixture
def diary_entry_with_values(
    diary_entry: DiaryEntry,
    metric_number: Metric,
    metric_boolean: Metric,
) -> DiaryEntry:
    """Создаёт запись дневника с числовым и булевым значениями метрик."""
    DiaryEntryValue.objects.create(entry=diary_entry, metric=metric_number, value_number=5.5)
    DiaryEntryValue.objects.create(entry=diary_entry, metric=metric_boolean, value_boolean=True)
    return diary_entry
