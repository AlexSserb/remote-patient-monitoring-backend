"""Юнит-тесты кастомных классов прав доступа из config.permissions."""

from __future__ import annotations

from unittest.mock import MagicMock

from apps.users.models import Role
from config.permissions import IsCaregiver, IsDoctor, IsDoctorOrCaregiver, IsPatient


def _request(role: str | None = None) -> MagicMock:
    """Возвращает мок запроса с пользователем, у которого задана роль."""
    user = MagicMock()
    user.role = role
    request = MagicMock()
    request.user = user
    return request


def _anonymous_request() -> MagicMock:
    """Возвращает мок запроса без атрибута role (имитация AnonymousUser)."""
    user = MagicMock(spec=[])
    request = MagicMock()
    request.user = user
    return request


class TestIsDoctorOrCaregiver:
    """Тесты разрешения IsDoctorOrCaregiver."""

    def test_allows_doctor(self) -> None:
        """Возвращает True для пользователя с ролью доктора."""
        assert IsDoctorOrCaregiver().has_permission(_request(Role.DOCTOR), MagicMock()) is True

    def test_allows_caregiver(self) -> None:
        """Возвращает True для пользователя с ролью опекуна."""
        assert IsDoctorOrCaregiver().has_permission(_request(Role.CAREGIVER), MagicMock()) is True

    def test_denies_patient(self) -> None:
        """Возвращает False для пользователя с ролью пациента."""
        assert IsDoctorOrCaregiver().has_permission(_request(Role.PATIENT), MagicMock()) is False

    def test_denies_user_without_role_attribute(self) -> None:
        """Возвращает False, если у пользователя нет атрибута role (например, AnonymousUser)."""
        assert IsDoctorOrCaregiver().has_permission(_anonymous_request(), MagicMock()) is False


class TestIsDoctor:
    """Тесты разрешения IsDoctor."""

    def test_allows_doctor(self) -> None:
        """Возвращает True для пользователя с ролью доктора."""
        assert IsDoctor().has_permission(_request(Role.DOCTOR), MagicMock()) is True

    def test_denies_caregiver(self) -> None:
        """Возвращает False для опекуна."""
        assert IsDoctor().has_permission(_request(Role.CAREGIVER), MagicMock()) is False

    def test_denies_patient(self) -> None:
        """Возвращает False для пациента."""
        assert IsDoctor().has_permission(_request(Role.PATIENT), MagicMock()) is False

    def test_denies_user_without_role_attribute(self) -> None:
        """Возвращает False, если у пользователя нет атрибута role."""
        assert IsDoctor().has_permission(_anonymous_request(), MagicMock()) is False


class TestIsCaregiver:
    """Тесты разрешения IsCaregiver."""

    def test_allows_caregiver(self) -> None:
        """Возвращает True для пользователя с ролью опекуна."""
        assert IsCaregiver().has_permission(_request(Role.CAREGIVER), MagicMock()) is True

    def test_denies_doctor(self) -> None:
        """Возвращает False для доктора."""
        assert IsCaregiver().has_permission(_request(Role.DOCTOR), MagicMock()) is False

    def test_denies_patient(self) -> None:
        """Возвращает False для пациента."""
        assert IsCaregiver().has_permission(_request(Role.PATIENT), MagicMock()) is False

    def test_denies_user_without_role_attribute(self) -> None:
        """Возвращает False, если у пользователя нет атрибута role."""
        assert IsCaregiver().has_permission(_anonymous_request(), MagicMock()) is False


class TestIsPatient:
    """Тесты разрешения IsPatient."""

    def test_allows_patient(self) -> None:
        """Возвращает True для пользователя с ролью пациента."""
        assert IsPatient().has_permission(_request(Role.PATIENT), MagicMock()) is True

    def test_denies_doctor(self) -> None:
        """Возвращает False для доктора."""
        assert IsPatient().has_permission(_request(Role.DOCTOR), MagicMock()) is False

    def test_denies_caregiver(self) -> None:
        """Возвращает False для опекуна."""
        assert IsPatient().has_permission(_request(Role.CAREGIVER), MagicMock()) is False

    def test_denies_user_without_role_attribute(self) -> None:
        """Возвращает False, если у пользователя нет атрибута role."""
        assert IsPatient().has_permission(_anonymous_request(), MagicMock()) is False
