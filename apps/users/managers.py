"""Менеджер пользовательской модели."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.contrib.auth.base_user import BaseUserManager

if TYPE_CHECKING:
    from apps.users.models import User


class UserManager(BaseUserManager["User"]):
    """Менеджер пользователей с аутентификацией по email вместо username."""

    def create_user(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: Any,
    ) -> User:
        """Создаёт и сохраняет обычного пользователя с заданным email и паролем."""
        if not email:
            msg = "Email обязателен для создания пользователя"
            raise ValueError(msg)
        email = self.normalize_email(email)
        user: User = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: Any,
    ) -> User:
        """Создаёт суперпользователя с полными правами администратора."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            msg = "Суперпользователь должен иметь is_staff=True"
            raise ValueError(msg)
        if extra_fields.get("is_superuser") is not True:
            msg = "Суперпользователь должен иметь is_superuser=True"
            raise ValueError(msg)

        return self.create_user(email, password, **extra_fields)
