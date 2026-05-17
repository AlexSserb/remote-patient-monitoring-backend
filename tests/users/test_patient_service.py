"""Юнит-тесты PatientService — репозитории замещены моками."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from rest_framework.exceptions import PermissionDenied

from apps.users.models import Role
from apps.users.services import PatientService


def _user(pk: int = 1, role: str = Role.DOCTOR) -> MagicMock:
    """Возвращает мок пользователя с заданным pk и ролью."""
    return MagicMock(pk=pk, role=role)


def _repo() -> MagicMock:
    """Возвращает свежий мок PatientRepository."""
    return MagicMock()


def _user_repo() -> MagicMock:
    """Возвращает свежий мок UserRepository."""
    return MagicMock()


class TestListPatients:
    """Тесты получения постраничного списка пациентов."""

    def test_applies_role_filter_and_value_filters(self) -> None:
        """Вызывает apply_role_filter и apply_filters и возвращает результат apply_filters с total."""
        repo = _repo()
        user_repo = _user_repo()
        user = _user(role=Role.DOCTOR)
        base_qs = MagicMock()
        role_filtered = MagicMock()
        filtered = MagicMock()
        filtered.count.return_value = 0
        filtered.order_by.return_value.__getitem__ = MagicMock(return_value=[])
        user_repo.get_patients_base_qs.return_value = base_qs
        repo.apply_role_filter.return_value = role_filtered
        repo.apply_filters.return_value = filtered
        params = MagicMock()
        params.get.return_value = "false"
        params.getlist.return_value = []
        _patients, _total = PatientService(repo=repo, user_repo=user_repo).list_patients(user, params)
        repo.apply_role_filter.assert_called_once_with(base_qs, user, attached=False)
        repo.apply_filters.assert_called_once()

    def test_returns_total_from_qs_count(self) -> None:
        """Возвращаемый total соответствует count() отфильтрованного QuerySet."""
        repo = _repo()
        user_repo = _user_repo()
        qs = MagicMock()
        qs.count.return_value = 5
        qs.order_by.return_value.__getitem__ = MagicMock(return_value=[])
        user_repo.get_patients_base_qs.return_value = MagicMock()
        repo.apply_role_filter.return_value = MagicMock()
        repo.apply_filters.return_value = qs
        params = MagicMock()
        params.get.return_value = "false"
        params.getlist.return_value = []
        _, total = PatientService(repo=repo, user_repo=user_repo).list_patients(_user(), params)
        assert total == 5


class TestEditPatient:
    """Тесты редактирования данных пациента доктором."""

    def test_raises_http404_when_patient_not_found(self) -> None:
        """Бросает Http404, если пациент с указанным ID не существует."""
        repo = _repo()
        repo.get_patient_by_id.side_effect = ObjectDoesNotExist
        with pytest.raises(Http404):
            PatientService(repo=repo).edit_patient(_user(), 999, {})

    def test_raises_permission_denied_without_doctor_access(self) -> None:
        """Бросает PermissionDenied, если доктор не прикреплён к пациенту."""
        repo = _repo()
        repo.get_patient_by_id.return_value = MagicMock()
        repo.has_doctor_access.return_value = False
        with pytest.raises(PermissionDenied):
            PatientService(repo=repo).edit_patient(_user(), 1, {})

    def test_syncs_diagnoses_when_present_in_data(self) -> None:
        """Вызывает sync_diagnoses только если поле diagnoses передано в data."""
        repo = _repo()
        repo.has_doctor_access.return_value = True
        doctor = _user()
        patient = MagicMock()
        repo.get_patient_by_id.return_value = patient
        PatientService(repo=repo).edit_patient(doctor, 1, {"diagnoses": [1, 2]})
        repo.sync_diagnoses.assert_called_once_with(patient, [1, 2], assigned_by=doctor)

    def test_does_not_sync_diagnoses_when_absent_from_data(self) -> None:
        """Не вызывает sync_diagnoses, если поле diagnoses отсутствует в data."""
        repo = _repo()
        repo.has_doctor_access.return_value = True
        repo.get_patient_by_id.return_value = MagicMock()
        PatientService(repo=repo).edit_patient(_user(), 1, {"doctors": [3]})
        repo.sync_diagnoses.assert_not_called()

    def test_syncs_doctors_when_present_in_data(self) -> None:
        """Вызывает sync_doctors только если поле doctors передано в data."""
        repo = _repo()
        repo.has_doctor_access.return_value = True
        patient = MagicMock()
        repo.get_patient_by_id.return_value = patient
        PatientService(repo=repo).edit_patient(_user(), 1, {"doctors": [3, 4]})
        repo.sync_doctors.assert_called_once_with(patient, [3, 4])

    def test_does_not_sync_doctors_when_absent_from_data(self) -> None:
        """Не вызывает sync_doctors, если поле doctors отсутствует в data."""
        repo = _repo()
        repo.has_doctor_access.return_value = True
        repo.get_patient_by_id.return_value = MagicMock()
        PatientService(repo=repo).edit_patient(_user(), 1, {"diagnoses": [1]})
        repo.sync_doctors.assert_not_called()

    def test_returns_patient_with_details(self) -> None:
        """Возвращает результат get_with_details после синхронизации."""
        repo = _repo()
        repo.has_doctor_access.return_value = True
        patient = MagicMock()
        patient.pk = 7
        repo.get_patient_by_id.return_value = patient
        expected = MagicMock()
        repo.get_with_details.return_value = expected
        result = PatientService(repo=repo).edit_patient(_user(), 7, {})
        repo.get_with_details.assert_called_once_with(patient.pk)
        assert result is expected
