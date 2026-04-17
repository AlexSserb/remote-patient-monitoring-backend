"""Модели пользователей системы мониторинга."""

from __future__ import annotations

from typing import ClassVar

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from apps.users.managers import UserManager


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


class DoctorPatient(models.Model):
    """Связь между доктором и пациентом в системе мониторинга."""

    doctor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="doctor_patients",
        limit_choices_to={"role": Role.DOCTOR},
        verbose_name="Доктор",
    )
    patient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="patient_doctors",
        limit_choices_to={"role": Role.PATIENT},
        verbose_name="Пациент",
    )
    assigned_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата назначения")

    class Meta:
        """Метаданные модели связи доктор-пациент."""

        verbose_name = "Связь доктор-пациент"
        verbose_name_plural = "Связи доктор-пациент"
        unique_together = ("doctor", "patient")

    def __str__(self) -> str:
        """Возвращает строковое представление связи доктор-пациент."""
        return f"{self.doctor} → {self.patient}"


class CaregiverPatient(models.Model):
    """Связь между опекуном и пациентом в системе мониторинга."""

    caregiver = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="caregiver_patients",
        limit_choices_to={"role": Role.CAREGIVER},
        verbose_name="Опекун",
    )
    patient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="patient_caregivers",
        limit_choices_to={"role": Role.PATIENT},
        verbose_name="Пациент",
    )
    assigned_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата назначения")

    class Meta:
        """Метаданные модели связи опекун-пациент."""

        verbose_name = "Связь опекун-пациент"
        verbose_name_plural = "Связи опекун-пациент"
        unique_together = ("caregiver", "patient")

    def __str__(self) -> str:
        """Возвращает строковое представление связи опекун-пациент."""
        return f"{self.caregiver} → {self.patient}"
