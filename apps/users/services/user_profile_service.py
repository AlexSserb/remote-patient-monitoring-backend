"""Сервис управления профилями пользователей."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404

from apps.users.repositories import UserRepository

if TYPE_CHECKING:
    from django.db.models import QuerySet


class UserProfileService:
    """Управление профилем, email и паролем пользователя через репозиторий."""

    def __init__(self, repo: UserRepository | None = None) -> None:
        """Инициализирует сервис с переданным или дефолтным репозиторием."""
        self._repo = repo or UserRepository()

    def get_user(self, user_id: int) -> Any:
        """Возвращает пользователя по ID или бросает Http404."""
        try:
            return self._repo.get_by_id(user_id)
        except ObjectDoesNotExist as e:
            raise Http404 from e

    def update_profile(self, user_id: int, data: dict) -> Any:
        """Получает пользователя по ID, обновляет поля профиля и сохраняет изменения."""
        user = self.get_user(user_id)
        for field, value in data.items():
            setattr(user, field, value)
        self._repo.save(user)
        return user

    def apply_email_change(self, user_id: int, new_email: str) -> Any:
        """Получает пользователя по ID и применяет новый email к аккаунту."""
        user = self.get_user(user_id)
        self._repo.save_email(user, new_email)
        return user

    def apply_password_reset(self, user_id: int, new_password: str) -> None:
        """Получает пользователя по ID и устанавливает новый пароль."""
        user = self.get_user(user_id)
        self._repo.save_password(user, new_password)

    def list_doctors(self) -> QuerySet:
        """Возвращает всех докторов системы."""
        return self._repo.get_doctors()

    def list_caregivers(self) -> QuerySet:
        """Возвращает всех опекунов системы."""
        return self._repo.get_caregivers()
