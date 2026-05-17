"""Репозиторий пользователей системы."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.contrib.auth import get_user_model
from django.db.models import Count

from apps.users.models import Role

if TYPE_CHECKING:
    from django.db.models import QuerySet

UserModel = get_user_model()


class UserRepository:
    """Репозиторий операций с моделью пользователя."""

    def get_by_id(self, user_id: int) -> Any:
        """Возвращает пользователя по первичному ключу или бросает DoesNotExist."""
        return UserModel.objects.get(pk=user_id)

    def save(self, user: Any) -> None:
        """Сохраняет изменения пользователя в базе данных."""
        user.save()

    def save_email(self, user: Any, new_email: str) -> None:
        """Устанавливает новый email и сохраняет только это поле."""
        user.email = new_email
        user.save(update_fields=["email"])

    def save_password(self, user: Any, new_password: str) -> None:
        """Устанавливает хэш нового пароля и сохраняет только это поле."""
        user.set_password(new_password)
        user.save(update_fields=["password"])

    def get_doctors(self) -> QuerySet:
        """Возвращает всех докторов, отсортированных по фамилии и имени."""
        return UserModel.objects.filter(role=Role.DOCTOR).order_by("last_name", "first_name")

    def get_caregivers(self) -> QuerySet:
        """Возвращает всех опекунов, отсортированных по фамилии и имени."""
        return UserModel.objects.filter(role=Role.CAREGIVER).order_by("last_name", "first_name")

    def get_patients_base_qs(self) -> QuerySet:
        """Возвращает базовый QuerySet пациентов с предзагрузкой связей и аннотацией количества опекунов."""
        return (
            UserModel.objects.filter(role=Role.PATIENT)
            .prefetch_related("diagnoses__diagnosis", "patient_doctors__doctor", "patient_caregivers__caregiver")
            .annotate(
                # distinct=True защищает от дублей строк при последующих JOIN-фильтрах
                caregiver_count=Count("patient_caregivers", distinct=True),
            )
        )
