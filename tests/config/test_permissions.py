"""Юнит-тесты кастомных классов прав доступа из config.permissions."""

from __future__ import annotations

from unittest.mock import MagicMock

from apps.users.models import Role
from config.permissions import IsDoctorOrCaregiver


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
        permission = IsDoctorOrCaregiver()
        assert permission.has_permission(_request(Role.DOCTOR), MagicMock()) is True

    def test_allows_caregiver(self) -> None:
        """Возвращает True для пользователя с ролью опекуна."""
        permission = IsDoctorOrCaregiver()
        assert permission.has_permission(_request(Role.CAREGIVER), MagicMock()) is True

    def test_denies_patient(self) -> None:
        """Возвращает False для пользователя с ролью пациента."""
        permission = IsDoctorOrCaregiver()
        assert permission.has_permission(_request(Role.PATIENT), MagicMock()) is False

    def test_denies_user_without_role_attribute(self) -> None:
        """Возвращает False, если у пользователя нет атрибута role (например, AnonymousUser)."""
        permission = IsDoctorOrCaregiver()
        assert permission.has_permission(_anonymous_request(), MagicMock()) is False
