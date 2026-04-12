"""Модели пользователей системы мониторинга."""

from __future__ import annotations

from typing import ClassVar

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from users.managers import UserManager


class Role(models.TextChoices):
    """Роли участников системы дистанционного мониторинга."""

    DOCTOR = "doctor", "Доктор"
    PATIENT = "patient", "Пациент"
    CAREGIVER = "caregiver", "Опекун"


class User(AbstractBaseUser, PermissionsMixin):
    """Пользователь системы с аутентификацией по email и ролевой моделью."""

    email = models.EmailField(unique=True, verbose_name="Email")
    first_name = models.CharField(max_length=150, verbose_name="Имя")
    last_name = models.CharField(max_length=150, verbose_name="Фамилия")
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        verbose_name="Роль",
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    is_staff = models.BooleanField(default=False, verbose_name="Персонал")
    date_joined = models.DateTimeField(auto_now_add=True, verbose_name="Дата регистрации")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = ["first_name", "last_name", "role"]

    objects: UserManager = UserManager()

    class Meta:
        """Метаданные модели пользователя."""

        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self) -> str:
        """Возвращает строковое представление пользователя в виде имени и email."""
        return f"{self.get_full_name()} <{self.email}>"

    def get_full_name(self) -> str:
        """Возвращает полное имя пользователя."""
        return f"{self.first_name} {self.last_name}".strip()
