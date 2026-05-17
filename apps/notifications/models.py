"""Модели системы уведомлений о заполнении дневника."""

from __future__ import annotations

from typing import ClassVar

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.users.models import Role


class NotificationChannel(models.TextChoices):
    """Канал доставки уведомления пользователю."""

    EMAIL = "email", "Email"
    WEB_PUSH = "web_push", "Web Push"


class NotificationStatus(models.TextChoices):
    """Статус уведомления в истории отправок."""

    SENT = "sent", "Отправлено"
    OPENED = "opened", "Открыто"
    COMPLETED = "completed", "Выполнено"
    IGNORED = "ignored", "Проигнорировано"


class NotificationSchedule(models.Model):
    """Расписание напоминаний получателя о заполнении дневника конкретного пациента."""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_schedules",
        limit_choices_to={"role__in": [Role.PATIENT, Role.CAREGIVER]},
        verbose_name="Получатель",
    )
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="patient_notification_schedules",
        limit_choices_to={"role": Role.PATIENT},
        verbose_name="Пациент",
    )
    # 0 — понедельник, 6 — воскресенье; соответствует datetime.weekday()
    days_of_week = ArrayField(
        models.SmallIntegerField(
            validators=[MinValueValidator(0), MaxValueValidator(6)],
        ),
        verbose_name="Дни недели",
    )
    times = ArrayField(
        models.TimeField(),
        verbose_name="Время отправки",
    )
    is_enabled = models.BooleanField(default=True, verbose_name="Включено")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        """Метаданные модели расписания уведомлений."""

        verbose_name = "Расписание уведомлений"
        verbose_name_plural = "Расписания уведомлений"
        unique_together = ("recipient", "patient")

    def __str__(self) -> str:
        """Возвращает строковое представление расписания уведомлений."""
        return f"NotificationSchedule(recipient={self.recipient_id}, patient={self.patient_id})"  # ty: ignore[unresolved-attribute]


class NotificationChannelConfig(models.Model):
    """Параметры конкретного канала доставки уведомлений для пользователя."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_channel_configs",
        verbose_name="Пользователь",
    )
    channel = models.CharField(
        max_length=20,
        choices=NotificationChannel.choices,
        verbose_name="Канал",
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    # структура зависит от канала: для web_push — endpoint/ключи, для email — переопределение адреса
    config = models.JSONField(default=dict, verbose_name="Конфигурация канала")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        """Метаданные модели конфигурации канала уведомлений."""

        verbose_name = "Канал уведомлений"
        verbose_name_plural = "Каналы уведомлений"
        unique_together = ("user", "channel")

    def __str__(self) -> str:
        """Возвращает строковое представление конфигурации канала."""
        return f"{self.user} / {self.channel}"


class NotificationRecord(models.Model):
    """Запись об отправленном уведомлении с историей статусов и реакцией пользователя."""

    # SET_NULL сохраняет историю при удалении расписания (нужно для ML-обучения)
    schedule = models.ForeignKey(
        NotificationSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="records",
        verbose_name="Расписание",
    )
    # recipient и patient денормализованы из расписания: история не теряется при SET_NULL выше
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_records",
        verbose_name="Получатель",
    )
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="patient_notification_records",
        limit_choices_to={"role": Role.PATIENT},
        verbose_name="Пациент",
    )
    channel = models.CharField(
        max_length=20,
        choices=NotificationChannel.choices,
        verbose_name="Канал",
    )
    channel_target = models.CharField(
        max_length=500,
        verbose_name="Адрес доставки",
    )
    status = models.CharField(
        max_length=20,
        choices=NotificationStatus.choices,
        default=NotificationStatus.SENT,
        verbose_name="Статус",
    )
    # явная оценка от пользователя; вычисляемые метрики считаются из временных меток
    reaction_score = models.SmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Оценка реакции",
    )
    sent_at = models.DateTimeField(auto_now_add=True, verbose_name="Отправлено")
    opened_at = models.DateTimeField(null=True, blank=True, verbose_name="Открыто")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Выполнено")
    # ссылка на запись дневника, созданную после уведомления — ключевой признак для ML
    diary_entry = models.ForeignKey(
        "diagnoses.DiaryEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_by",
        verbose_name="Запись дневника",
    )
    metadata = models.JSONField(default=dict, verbose_name="Метаданные")

    class Meta:
        """Метаданные модели истории уведомлений."""

        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"
        ordering: ClassVar = ["-sent_at"]
        indexes: ClassVar = [
            # история получателя в хронологическом порядке
            models.Index(fields=["recipient", "-sent_at"], name="notifrecord_recipient_sent_idx"),
            # аналитика уведомлений в разрезе пациента
            models.Index(fields=["patient", "-sent_at"], name="notifrecord_patient_sent_idx"),
            # Celery-задача ищет записи в статусе sent для перевода в ignored по таймауту
            models.Index(fields=["status", "sent_at"], name="notifrecord_status_sent_idx"),
        ]

    def __str__(self) -> str:
        """Возвращает строковое представление записи уведомления."""
        return f"NotificationRecord(recipient={self.recipient_id}, channel={self.channel}, sent_at={self.sent_at})"  # ty: ignore[unresolved-attribute]
