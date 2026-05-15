"""Тесты репозиториев системы уведомлений — прямые обращения к БД."""

from __future__ import annotations

from datetime import time
from typing import ClassVar

import pytest

from apps.notifications.models import NotificationChannel, NotificationChannelConfig, NotificationSchedule
from apps.notifications.repositories import ChannelConfigRepository, ScheduleRepository
from apps.users.models import User


@pytest.mark.django_db
class TestScheduleRepositoryGetPatient:
    """Тесты получения пациента из базы данных."""

    def test_returns_user_with_patient_role(self, patient: User) -> None:
        """Возвращает пользователя с ролью пациента по корректному ID."""
        result = ScheduleRepository().get_patient(patient.pk)
        assert result == patient

    def test_raises_for_non_patient_role(self, doctor: User) -> None:
        """Бросает DoesNotExist, если пользователь не является пациентом."""
        with pytest.raises(User.DoesNotExist):
            ScheduleRepository().get_patient(doctor.pk)

    def test_raises_for_nonexistent_id(self) -> None:
        """Бросает DoesNotExist для несуществующего ID."""
        with pytest.raises(User.DoesNotExist):
            ScheduleRepository().get_patient(999999)


@pytest.mark.django_db
class TestScheduleRepositoryGetForPatient:
    """Тесты получения расписаний для пациента."""

    def test_returns_schedules_of_given_patient(self, schedule: NotificationSchedule, patient: User) -> None:
        """Возвращает расписания, привязанные к указанному пациенту."""
        assert schedule in list(ScheduleRepository().get_for_patient(patient))

    def test_excludes_other_patient_schedules(self, schedule: NotificationSchedule, other_patient: User) -> None:
        """Не возвращает расписания другого пациента."""
        assert schedule not in list(ScheduleRepository().get_for_patient(other_patient))


@pytest.mark.django_db
class TestScheduleRepositoryFilterForUser:
    """Тесты фильтрации расписаний по роли пользователя."""

    def test_patient_sees_own_schedule_only(
        self, schedule: NotificationSchedule, patient: User, caregiver: User
    ) -> None:
        """Пациент видит только своё расписание, не расписание опекуна."""
        caregiver_schedule = NotificationSchedule.objects.create(
            recipient=caregiver,
            patient=patient,
            days_of_week=[0],
            times=[time(10, 0)],
        )
        repo = ScheduleRepository()
        result = list(repo.filter_for_user(repo.get_for_patient(patient), patient, patient))
        assert schedule in result
        assert caregiver_schedule not in result

    def test_caregiver_sees_own_and_patient_schedules(
        self, schedule: NotificationSchedule, patient: User, caregiver: User
    ) -> None:
        """Опекун видит своё расписание и расписание самого пациента."""
        caregiver_schedule = NotificationSchedule.objects.create(
            recipient=caregiver,
            patient=patient,
            days_of_week=[0],
            times=[time(10, 0)],
        )
        repo = ScheduleRepository()
        result = list(repo.filter_for_user(repo.get_for_patient(patient), caregiver, patient))
        assert schedule in result
        assert caregiver_schedule in result

    def test_doctor_sees_all_schedules(
        self, schedule: NotificationSchedule, patient: User, caregiver: User, doctor: User
    ) -> None:
        """Доктор видит все расписания пациента, включая расписания опекунов."""
        caregiver_schedule = NotificationSchedule.objects.create(
            recipient=caregiver,
            patient=patient,
            days_of_week=[0],
            times=[time(10, 0)],
        )
        repo = ScheduleRepository()
        result = list(repo.filter_for_user(repo.get_for_patient(patient), doctor, patient))
        assert schedule in result
        assert caregiver_schedule in result


@pytest.mark.django_db
class TestScheduleRepositoryGetById:
    """Тесты получения расписания по ID."""

    def test_returns_schedule_by_id(self, schedule: NotificationSchedule) -> None:
        """Возвращает расписание по существующему ID."""
        result = ScheduleRepository().get_by_id(schedule.pk)
        assert result.pk == schedule.pk

    def test_raises_for_nonexistent_id(self) -> None:
        """Бросает DoesNotExist для несуществующего ID."""
        with pytest.raises(NotificationSchedule.DoesNotExist):
            ScheduleRepository().get_by_id(999999)


@pytest.mark.django_db
class TestScheduleRepositoryUpsert:
    """Тесты создания и обновления расписания через upsert."""

    def test_creates_new_schedule(self, patient: User) -> None:
        """Создаёт новое расписание, если запись для пары получатель-пациент не существует."""
        data = {"days_of_week": [0, 1], "times": [time(8, 0)], "is_enabled": True}
        result, created = ScheduleRepository().upsert(patient, patient, data)
        assert created is True
        assert result.recipient == patient
        assert result.days_of_week == [0, 1]

    def test_updates_existing_schedule(self, schedule: NotificationSchedule, patient: User) -> None:
        """Обновляет существующее расписание без создания дубликата."""
        data = {"days_of_week": [6], "times": [time(12, 0)], "is_enabled": False}
        result, created = ScheduleRepository().upsert(patient, patient, data)
        assert created is False
        assert result.pk == schedule.pk
        assert result.days_of_week == [6]
        assert result.is_enabled is False


@pytest.mark.django_db
class TestScheduleRepositorySave:
    """Тесты сохранения изменений расписания."""

    def test_persists_field_change(self, schedule: NotificationSchedule) -> None:
        """Изменение поля сохраняется в БД и видно при повторном чтении."""
        schedule.is_enabled = False
        ScheduleRepository().save(schedule)
        assert NotificationSchedule.objects.get(pk=schedule.pk).is_enabled is False


@pytest.mark.django_db
class TestScheduleRepositoryAccessChecks:
    """Тесты проверки связей опекун/доктор-пациент."""

    def test_has_caregiver_access_true_when_linked(
        self, caregiver: User, patient: User, caregiver_patient: object
    ) -> None:
        """Возвращает True для опекуна, привязанного к пациенту."""
        assert ScheduleRepository().has_caregiver_access(caregiver, patient.pk) is True

    def test_has_caregiver_access_false_when_not_linked(self, caregiver: User, patient: User) -> None:
        """Возвращает False для опекуна без связи с пациентом."""
        assert ScheduleRepository().has_caregiver_access(caregiver, patient.pk) is False

    def test_has_doctor_access_true_when_linked(self, doctor: User, patient: User, doctor_patient: object) -> None:
        """Возвращает True для доктора, привязанного к пациенту."""
        assert ScheduleRepository().has_doctor_access(doctor, patient.pk) is True

    def test_has_doctor_access_false_when_not_linked(self, doctor: User, patient: User) -> None:
        """Возвращает False для доктора без связи с пациентом."""
        assert ScheduleRepository().has_doctor_access(doctor, patient.pk) is False


@pytest.mark.django_db
class TestChannelConfigRepository:
    """Тесты репозитория конфигурации каналов уведомлений."""

    _SUB: ClassVar[dict] = {
        "endpoint": "https://push.example.com/sub123",
        "keys": {"p256dh": "key1", "auth": "auth1"},
    }

    def test_upsert_creates_new_subscription(self, patient: User) -> None:
        """Создаёт новую запись конфигурации при отсутствии существующей."""
        ChannelConfigRepository().upsert_push_subscription(patient, self._SUB)
        cfg = NotificationChannelConfig.objects.get(user=patient, channel=NotificationChannel.WEB_PUSH)
        assert cfg.is_active is True
        assert cfg.config == self._SUB

    def test_upsert_updates_existing_subscription(self, patient: User) -> None:
        """Обновляет endpoint существующей подписки без создания дубликата."""
        ChannelConfigRepository().upsert_push_subscription(patient, self._SUB)
        new_sub = {**self._SUB, "endpoint": "https://push.example.com/new"}
        ChannelConfigRepository().upsert_push_subscription(patient, new_sub)
        assert NotificationChannelConfig.objects.filter(user=patient, channel=NotificationChannel.WEB_PUSH).count() == 1
        assert (
            NotificationChannelConfig.objects.get(user=patient, channel=NotificationChannel.WEB_PUSH).config["endpoint"]
            == "https://push.example.com/new"
        )

    def test_upsert_reactivates_inactive_subscription(self, patient: User) -> None:
        """Повторная подписка реактивирует ранее деактивированную запись."""
        NotificationChannelConfig.objects.create(
            user=patient,
            channel=NotificationChannel.WEB_PUSH,
            config=self._SUB,
            is_active=False,
        )
        ChannelConfigRepository().upsert_push_subscription(patient, self._SUB)
        assert (
            NotificationChannelConfig.objects.get(user=patient, channel=NotificationChannel.WEB_PUSH).is_active is True
        )

    def test_deactivate_sets_is_active_false(self, patient: User) -> None:
        """Деактивация устанавливает is_active=False без удаления записи."""
        ChannelConfigRepository().upsert_push_subscription(patient, self._SUB)
        ChannelConfigRepository().deactivate_push_subscription(patient)
        assert (
            NotificationChannelConfig.objects.get(user=patient, channel=NotificationChannel.WEB_PUSH).is_active is False
        )

    def test_deactivate_is_noop_when_no_subscription(self, patient: User) -> None:
        """Деактивация при отсутствии подписки не вызывает исключений."""
        ChannelConfigRepository().deactivate_push_subscription(patient)
