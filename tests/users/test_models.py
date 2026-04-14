"""Тесты модели User и перечисления Role."""

from __future__ import annotations

import pytest
from django.db import IntegrityError

from users.models import Role, User

pytestmark = pytest.mark.django_db


class TestRole:
    """Тесты перечисления ролей участников системы."""

    def test_doctor_value(self) -> None:
        """Роль доктора имеет корректное строковое значение."""
        assert Role.DOCTOR == "doctor"

    def test_patient_value(self) -> None:
        """Роль пациента имеет корректное строковое значение."""
        assert Role.PATIENT == "patient"

    def test_caregiver_value(self) -> None:
        """Роль опекуна имеет корректное строковое значение."""
        assert Role.CAREGIVER == "caregiver"

    def test_all_roles_present(self) -> None:
        """В перечислении присутствуют все три роли."""
        values = {r.value for r in Role}
        assert values == {"doctor", "patient", "caregiver"}


class TestUserModel:
    """Тесты кастомной модели пользователя."""

    def test_str_returns_name_and_email(self, user: User) -> None:
        """Строковое представление содержит полное имя и email в угловых скобках."""
        assert str(user) == "Иван Иванов <patient@example.com>"

    def test_get_full_name_both_parts(self, user: User) -> None:
        """Полное имя формируется из имени и фамилии через пробел."""
        assert user.get_full_name() == "Иван Иванов"

    def test_get_full_name_strips_whitespace(self, db: None) -> None:
        """Полное имя не содержит лишних пробелов при пустом поле."""
        user = User.objects.create_user(
            email="nolast@example.com",
            password="Pass123!",
            first_name="Анна",
            last_name="",
            role=Role.PATIENT,
        )
        assert user.get_full_name() == "Анна"

    def test_username_field_is_email(self) -> None:
        """Поле аутентификации — email, а не username."""
        assert User.USERNAME_FIELD == "email"

    def test_required_fields(self) -> None:
        """REQUIRED_FIELDS содержит имя, фамилию и роль."""
        assert set(User.REQUIRED_FIELDS) == {"first_name", "last_name", "role"}

    def test_is_active_default_true(self, user: User) -> None:
        """Новый пользователь активен по умолчанию."""
        assert user.is_active is True

    def test_is_staff_default_false(self, user: User) -> None:
        """Новый пользователь не является персоналом по умолчанию."""
        assert user.is_staff is False

    def test_email_unique_constraint(self, user: User) -> None:
        """Попытка создать второго пользователя с тем же email вызывает IntegrityError."""
        with pytest.raises(IntegrityError):
            User.objects.create_user(
                email=user.email,
                password="AnotherPass123!",
                first_name="Дубль",
                last_name="Дублев",
                role=Role.PATIENT,
            )

    def test_date_joined_set_on_create(self, user: User) -> None:
        """Дата регистрации заполняется автоматически при создании."""
        assert user.date_joined is not None
