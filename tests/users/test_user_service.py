"""Юнит-тесты UserProfileService — репозиторий замещён моком."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404

from apps.users.services import UserProfileService


def _repo() -> MagicMock:
    """Возвращает свежий мок репозитория для каждого теста."""
    return MagicMock()


class TestGetUser:
    """Тесты получения пользователя по ID."""

    def test_returns_user_when_found(self) -> None:
        """При успешном запросе возвращает объект пользователя из репозитория."""
        repo = _repo()
        expected = MagicMock()
        repo.get_by_id.return_value = expected
        result = UserProfileService(repo=repo).get_user(1)
        assert result is expected
        repo.get_by_id.assert_called_once_with(1)

    def test_raises_http404_when_not_found(self) -> None:
        """Бросает Http404, если пользователь с указанным ID не существует."""
        repo = _repo()
        repo.get_by_id.side_effect = ObjectDoesNotExist
        with pytest.raises(Http404):
            UserProfileService(repo=repo).get_user(999)


class TestUpdateProfile:
    """Тесты обновления профиля пользователя."""

    def test_sets_fields_and_saves(self) -> None:
        """Устанавливает переданные поля и вызывает сохранение через репозиторий."""
        repo = _repo()
        user = MagicMock()
        repo.get_by_id.return_value = user
        UserProfileService(repo=repo).update_profile(1, {"first_name": "Иван", "last_name": "Иванов"})
        assert user.first_name == "Иван"
        assert user.last_name == "Иванов"
        repo.save.assert_called_once_with(user)

    def test_returns_updated_user(self) -> None:
        """Возвращает объект пользователя после обновления."""
        repo = _repo()
        user = MagicMock()
        repo.get_by_id.return_value = user
        result = UserProfileService(repo=repo).update_profile(1, {"first_name": "Иван"})
        assert result is user

    def test_raises_http404_when_user_not_found(self) -> None:
        """Бросает Http404, если пользователь с указанным ID не существует."""
        repo = _repo()
        repo.get_by_id.side_effect = ObjectDoesNotExist
        with pytest.raises(Http404):
            UserProfileService(repo=repo).update_profile(999, {"first_name": "X"})


class TestApplyEmailChange:
    """Тесты применения нового email."""

    def test_delegates_save_email_to_repo(self) -> None:
        """Передаёт пользователя и новый email в репозиторий."""
        repo = _repo()
        user = MagicMock()
        repo.get_by_id.return_value = user
        UserProfileService(repo=repo).apply_email_change(1, "new@example.com")
        repo.save_email.assert_called_once_with(user, "new@example.com")

    def test_returns_user(self) -> None:
        """Возвращает объект пользователя после смены email."""
        repo = _repo()
        user = MagicMock()
        repo.get_by_id.return_value = user
        result = UserProfileService(repo=repo).apply_email_change(1, "new@example.com")
        assert result is user

    def test_raises_http404_when_user_not_found(self) -> None:
        """Бросает Http404, если пользователь с указанным ID не существует."""
        repo = _repo()
        repo.get_by_id.side_effect = ObjectDoesNotExist
        with pytest.raises(Http404):
            UserProfileService(repo=repo).apply_email_change(999, "new@example.com")


class TestApplyPasswordReset:
    """Тесты применения нового пароля."""

    def test_delegates_save_password_to_repo(self) -> None:
        """Передаёт пользователя и новый пароль в репозиторий."""
        repo = _repo()
        user = MagicMock()
        repo.get_by_id.return_value = user
        UserProfileService(repo=repo).apply_password_reset(1, "NewPass123!")
        repo.save_password.assert_called_once_with(user, "NewPass123!")

    def test_raises_http404_when_user_not_found(self) -> None:
        """Бросает Http404, если пользователь с указанным ID не существует."""
        repo = _repo()
        repo.get_by_id.side_effect = ObjectDoesNotExist
        with pytest.raises(Http404):
            UserProfileService(repo=repo).apply_password_reset(999, "NewPass123!")


class TestListDoctors:
    """Тесты получения списка докторов."""

    def test_delegates_to_repo(self) -> None:
        """Возвращает QuerySet докторов из репозитория."""
        repo = _repo()
        expected = MagicMock()
        repo.get_doctors.return_value = expected
        result = UserProfileService(repo=repo).list_doctors()
        assert result is expected


class TestListCaregivers:
    """Тесты получения списка опекунов."""

    def test_delegates_to_repo(self) -> None:
        """Возвращает QuerySet опекунов из репозитория."""
        repo = _repo()
        expected = MagicMock()
        repo.get_caregivers.return_value = expected
        result = UserProfileService(repo=repo).list_caregivers()
        assert result is expected
