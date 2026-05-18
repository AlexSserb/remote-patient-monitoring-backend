"""Юнит-тесты DiagnosisService — репозиторий замещён моком."""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

import pytest
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.diagnoses.services import DiagnosisService
from apps.users.models import Role


def _user(role: str = Role.PATIENT) -> MagicMock:
    """Возвращает мок пользователя с заданной ролью."""
    return MagicMock(role=role)


def _repo() -> MagicMock:
    """Возвращает свежий мок DiagnosisRepository."""
    return MagicMock()


class TestResolveDiaryPatient:
    """Тесты разрешения пациента для операций с дневником."""

    def test_patient_returns_self(self) -> None:
        """Пациент получает доступ к собственному дневнику без patient_id."""
        user = _user(Role.PATIENT)
        repo = _repo()
        DiagnosisService(repo=repo).get_diary_fields(user, None)
        repo.get_diary_fields.assert_called_once_with(user)

    def test_caregiver_without_patient_id_raises_validation_error(self) -> None:
        """Опекун без patient_id получает ValidationError."""
        with pytest.raises(ValidationError):
            DiagnosisService(repo=_repo()).get_diary_fields(_user(Role.CAREGIVER), None)

    def test_caregiver_with_non_integer_patient_id_raises_validation_error(self) -> None:
        """Опекун с нечисловым patient_id получает ValidationError."""
        with pytest.raises(ValidationError):
            DiagnosisService(repo=_repo()).get_diary_fields(_user(Role.CAREGIVER), "abc")

    def test_caregiver_without_access_raises_permission_denied(self) -> None:
        """Опекун без связи с пациентом получает PermissionDenied."""
        repo = _repo()
        repo.has_caregiver_access.return_value = False
        with pytest.raises(PermissionDenied):
            DiagnosisService(repo=repo).get_diary_fields(_user(Role.CAREGIVER), "5")

    def test_caregiver_with_access_gets_patient_fields(self) -> None:
        """Опекун с доступом получает поля дневника своего пациента."""
        repo = _repo()
        repo.has_caregiver_access.return_value = True
        patient = MagicMock()
        repo.get_patient_by_id.return_value = patient
        DiagnosisService(repo=repo).get_diary_fields(_user(Role.CAREGIVER), "5")
        repo.has_caregiver_access.assert_called_once()
        repo.get_diary_fields.assert_called_once_with(patient)

    def test_doctor_raises_permission_denied(self) -> None:
        """Доктор не имеет доступа к дневниковым операциям."""
        with pytest.raises(PermissionDenied):
            DiagnosisService(repo=_repo()).get_diary_fields(_user(Role.DOCTOR), "1")


class TestResolveAnalyticsPatient:
    """Тесты разрешения пациента для аналитики."""

    def _call(self, user: MagicMock, patient_id: int | None, repo: MagicMock) -> None:
        """Вызывает get_analytics для проверки разрешения пациента."""
        today = datetime.datetime.now(tz=datetime.UTC).date()
        DiagnosisService(repo=repo).get_analytics(user, patient_id, today, today, [])

    def test_doctor_without_patient_id_raises_validation_error(self) -> None:
        """Доктор без patient_id получает ValidationError."""
        with pytest.raises(ValidationError):
            self._call(_user(Role.DOCTOR), None, _repo())

    def test_doctor_without_access_raises_permission_denied(self) -> None:
        """Доктор без связи с пациентом получает PermissionDenied."""
        repo = _repo()
        repo.has_doctor_access.return_value = False
        with pytest.raises(PermissionDenied):
            self._call(_user(Role.DOCTOR), 3, repo)

    def test_doctor_with_access_resolves_patient(self) -> None:
        """Доктор с доступом получает пациента через репозиторий."""
        repo = _repo()
        repo.has_doctor_access.return_value = True
        patient = MagicMock()
        repo.get_patient_by_id.return_value = patient
        repo.get_analytics_metrics.return_value = MagicMock()
        self._call(_user(Role.DOCTOR), 3, repo)
        repo.has_doctor_access.assert_called_once()
        repo.get_patient_by_id.assert_called_once_with(3)


class TestCreateDiaryEntry:
    """Тесты создания записи дневника."""

    def test_creates_entry_and_bulk_creates_values(self) -> None:
        """Создаёт запись и передаёт значения метрик в bulk_create_values."""
        repo = _repo()
        user = _user(Role.PATIENT)
        entry = MagicMock()
        repo.create_diary_entry.return_value = entry
        values = [{"metric_id": 1, "value_number": 5.5}]
        DiagnosisService(repo=repo).create_diary_entry(user, None, {"values": values})
        repo.create_diary_entry.assert_called_once_with(user, author=user)
        repo.bulk_create_values.assert_called_once_with(entry, values)

    def test_returns_entry_with_values(self) -> None:
        """Возвращает запись с предзагруженными значениями после создания."""
        repo = _repo()
        entry = MagicMock()
        repo.create_diary_entry.return_value = entry
        expected = MagicMock()
        repo.get_entry_with_values.return_value = expected
        result = DiagnosisService(repo=repo).create_diary_entry(_user(Role.PATIENT), None, {"values": []})
        repo.get_entry_with_values.assert_called_once_with(entry.pk)
        assert result is expected


class TestUpdateDiaryEntry:
    """Тесты обновления записи дневника."""

    def test_upserts_each_value(self) -> None:
        """Вызывает upsert_entry_value для каждого значения в data."""
        repo = _repo()
        repo.get_entry_for_patient.return_value = MagicMock()
        values = [{"metric_id": 1, "value_number": 6.0}, {"metric_id": 2, "value_boolean": True}]
        DiagnosisService(repo=repo).update_diary_entry(_user(Role.PATIENT), None, 1, {"values": values})
        assert repo.upsert_entry_value.call_count == 2

    def test_returns_entry_with_values(self) -> None:
        """Возвращает обновлённую запись с предзагруженными значениями."""
        repo = _repo()
        repo.get_entry_for_patient.return_value = MagicMock()
        expected = MagicMock()
        repo.get_entry_with_values.return_value = expected
        result = DiagnosisService(repo=repo).update_diary_entry(_user(Role.PATIENT), None, 1, {"values": []})
        assert result is expected


class TestDeleteDiaryEntry:
    """Тесты удаления записи дневника."""

    def test_deletes_resolved_entry(self) -> None:
        """Вызывает delete_entry для записи, принадлежащей пациенту."""
        repo = _repo()
        entry = MagicMock()
        repo.get_entry_for_patient.return_value = entry
        DiagnosisService(repo=repo).delete_diary_entry(_user(Role.PATIENT), None, 1)
        repo.delete_entry.assert_called_once_with(entry)


class TestGetAnalytics:
    """Тесты получения аналитики."""

    def test_returns_metrics_and_empty_data_points_when_no_metric_ids(self) -> None:
        """Возвращает доступные метрики и пустой список точек данных, если metric_ids не переданы."""
        repo = _repo()
        metrics_qs = MagicMock()
        repo.get_analytics_metrics.return_value = metrics_qs
        today = datetime.datetime.now(tz=datetime.UTC).date()
        available, data_points = DiagnosisService(repo=repo).get_analytics(_user(Role.PATIENT), None, today, today, [])
        assert available is metrics_qs
        assert data_points == []
        repo.get_analytics_data_points.assert_not_called()

    def test_calls_data_points_when_metric_ids_provided(self) -> None:
        """Вызывает get_analytics_data_points, если metric_ids непустой."""
        repo = _repo()
        repo.get_analytics_metrics.return_value = MagicMock()
        data_qs = MagicMock()
        repo.get_analytics_data_points.return_value = data_qs
        today = datetime.datetime.now(tz=datetime.UTC).date()
        _available, data_points = DiagnosisService(repo=repo).get_analytics(
            _user(Role.PATIENT), None, today, today, [1, 2]
        )
        repo.get_analytics_data_points.assert_called_once()
        assert data_points is data_qs
