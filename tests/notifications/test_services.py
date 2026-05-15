"""Юнит-тесты сервисов системы уведомлений — репозитории замещены моками."""

from __future__ import annotations

from datetime import time
from unittest.mock import MagicMock

import pytest
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.notifications.services import PushSubscriptionService, ScheduleService
from apps.users.models import Role


def _user(pk: int = 1, role: str = Role.PATIENT) -> MagicMock:
    """Возвращает мок пользователя с заданным pk и ролью."""
    return MagicMock(pk=pk, role=role)


def _schedule(recipient_id: int = 1, patient_id: int = 1) -> MagicMock:
    """Возвращает мок расписания с заданными recipient_id и patient_id."""
    return MagicMock(recipient_id=recipient_id, patient_id=patient_id)


def _data(**kwargs: object) -> dict:
    """Возвращает минимальный набор данных для создания расписания."""
    return {"patient_id": 1, "days_of_week": [0], "times": [time(9, 0)], "is_enabled": True, **kwargs}


class TestScheduleServiceListSchedules:
    """Тесты получения расписаний с проверкой прав доступа."""

    def test_raises_http404_when_patient_not_found(self) -> None:
        """Бросает Http404, если пациент с указанным ID не существует."""
        repo = MagicMock()
        repo.get_patient.side_effect = ObjectDoesNotExist
        with pytest.raises(Http404):
            ScheduleService(repo=repo).list_schedules(_user(), patient_id=999)

    def test_patient_denied_for_other_patient(self) -> None:
        """Пациент не может просматривать расписания другого пациента."""
        repo = MagicMock()
        repo.get_patient.return_value = _user(pk=2, role=Role.PATIENT)
        with pytest.raises(PermissionDenied):
            ScheduleService(repo=repo).list_schedules(_user(pk=1, role=Role.PATIENT), patient_id=2)

    def test_caregiver_denied_without_link(self) -> None:
        """Опекун без связи с пациентом получает PermissionDenied."""
        repo = MagicMock()
        repo.get_patient.return_value = _user(pk=2, role=Role.PATIENT)
        repo.has_caregiver_access.return_value = False
        with pytest.raises(PermissionDenied):
            ScheduleService(repo=repo).list_schedules(_user(pk=1, role=Role.CAREGIVER), patient_id=2)

    def test_doctor_denied_without_link(self) -> None:
        """Доктор без связи с пациентом получает PermissionDenied."""
        repo = MagicMock()
        repo.get_patient.return_value = _user(pk=2, role=Role.PATIENT)
        repo.has_doctor_access.return_value = False
        with pytest.raises(PermissionDenied):
            ScheduleService(repo=repo).list_schedules(_user(pk=1, role=Role.DOCTOR), patient_id=2)

    def test_returns_filter_for_user_result(self) -> None:
        """При наличии доступа возвращает результат filter_for_user из репозитория."""
        repo = MagicMock()
        patient = _user(pk=1, role=Role.PATIENT)
        repo.get_patient.return_value = patient
        expected = MagicMock()
        repo.filter_for_user.return_value = expected
        result = ScheduleService(repo=repo).list_schedules(patient, patient_id=1)
        assert result is expected


class TestScheduleServiceUpsert:
    """Тесты создания и обновления расписания."""

    def test_raises_http404_when_patient_not_found(self) -> None:
        """Бросает Http404, если пациент с указанным ID не существует."""
        repo = MagicMock()
        repo.get_patient.side_effect = ObjectDoesNotExist
        with pytest.raises(Http404):
            ScheduleService(repo=repo).upsert_schedule(_user(), _data())

    def test_raises_validation_error_when_doctor_omits_recipient_id(self) -> None:
        """Доктор без recipient_id получает ValidationError."""
        repo = MagicMock()
        repo.get_patient.return_value = _user(pk=2, role=Role.PATIENT)
        repo.has_doctor_access.return_value = True
        with pytest.raises(ValidationError):
            ScheduleService(repo=repo).upsert_schedule(_user(pk=1, role=Role.DOCTOR), _data(patient_id=2))

    def test_raises_validation_error_when_recipient_id_is_not_patient_or_self(self) -> None:
        """recipient_id, не совпадающий ни с пациентом, ни с самим пользователем, вызывает ValidationError."""
        repo = MagicMock()
        repo.get_patient.return_value = _user(pk=2, role=Role.PATIENT)
        repo.has_doctor_access.return_value = True
        with pytest.raises(ValidationError):
            ScheduleService(repo=repo).upsert_schedule(
                _user(pk=1, role=Role.DOCTOR), _data(patient_id=2, recipient_id=99)
            )

    def test_patient_cannot_set_other_as_recipient(self) -> None:
        """Пациент не может назначить другого получателя и получает PermissionDenied."""
        repo = MagicMock()
        patient = _user(pk=2, role=Role.PATIENT)
        repo.get_patient.return_value = patient
        with pytest.raises(PermissionDenied):
            ScheduleService(repo=repo).upsert_schedule(
                _user(pk=1, role=Role.PATIENT), _data(patient_id=2, recipient_id=2)
            )

    def test_caregiver_creates_own_schedule(self) -> None:
        """Опекун успешно создаёт расписание для себя; repo.upsert вызывается с опекуном как recipient."""
        repo = MagicMock()
        patient = _user(pk=2, role=Role.PATIENT)
        caregiver = _user(pk=1, role=Role.CAREGIVER)
        repo.get_patient.return_value = patient
        repo.has_caregiver_access.return_value = True
        repo.upsert.return_value = (MagicMock(), True)
        ScheduleService(repo=repo).upsert_schedule(caregiver, _data(patient_id=2))
        recipient_arg = repo.upsert.call_args.args[0]
        assert recipient_arg is caregiver

    def test_caregiver_creates_schedule_for_patient(self) -> None:
        """Опекун успешно создаёт расписание для пациента; repo.upsert вызывается с пациентом как recipient."""
        repo = MagicMock()
        patient = _user(pk=2, role=Role.PATIENT)
        caregiver = _user(pk=1, role=Role.CAREGIVER)
        repo.get_patient.return_value = patient
        repo.has_caregiver_access.return_value = True
        repo.upsert.return_value = (MagicMock(), True)
        ScheduleService(repo=repo).upsert_schedule(caregiver, _data(patient_id=2, recipient_id=2))
        recipient_arg = repo.upsert.call_args.args[0]
        assert recipient_arg is patient


class TestScheduleServicePatch:
    """Тесты частичного обновления расписания."""

    def test_raises_http404_when_schedule_not_found(self) -> None:
        """Бросает Http404, если расписание с указанным ID не существует."""
        repo = MagicMock()
        repo.get_by_id.side_effect = ObjectDoesNotExist
        with pytest.raises(Http404):
            ScheduleService(repo=repo).patch_schedule(_user(), schedule_id=999, data={})

    def test_raises_permission_denied_when_not_allowed(self) -> None:
        """Бросает PermissionDenied, если пациент не является владельцем расписания."""
        repo = MagicMock()
        repo.get_by_id.return_value = _schedule(recipient_id=2, patient_id=3)
        with pytest.raises(PermissionDenied):
            ScheduleService(repo=repo).patch_schedule(_user(pk=1, role=Role.PATIENT), schedule_id=1, data={})

    def test_applies_patch_data_and_saves(self) -> None:
        """Применяет переданные поля к объекту и вызывает repo.save."""
        repo = MagicMock()
        user = _user(pk=1, role=Role.PATIENT)
        schedule = _schedule(recipient_id=1, patient_id=1)
        repo.get_by_id.return_value = schedule
        ScheduleService(repo=repo).patch_schedule(user, schedule_id=1, data={"is_enabled": False})
        assert schedule.is_enabled is False
        repo.save.assert_called_once_with(schedule)


class TestPushSubscriptionService:
    """Тесты сервиса web push подписок."""

    def test_save_subscription_delegates_to_repo(self) -> None:
        """save_subscription передаёт пользователя и конфиг в репозиторий."""
        repo = MagicMock()
        user = _user()
        config = {"endpoint": "https://example.com", "keys": {}}
        PushSubscriptionService(repo=repo).save_subscription(user, config)
        repo.upsert_push_subscription.assert_called_once_with(user, config)

    def test_remove_subscription_delegates_to_repo(self) -> None:
        """remove_subscription передаёт пользователя в репозиторий для деактивации."""
        repo = MagicMock()
        user = _user()
        PushSubscriptionService(repo=repo).remove_subscription(user)
        repo.deactivate_push_subscription.assert_called_once_with(user)
