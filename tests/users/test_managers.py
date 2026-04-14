"""Тесты кастомного менеджера UserManager."""

from __future__ import annotations

import pytest

from users.models import Role, User

pytestmark = pytest.mark.django_db


class TestCreateUser:
    """Тесты метода create_user."""

    def test_creates_user_with_correct_email(self) -> None:
        """Пользователь создаётся с переданным email."""
        user = User.objects.create_user(
            email="user@example.com",
            password="Pass123!",
            first_name="Тест",
            last_name="Тестов",
            role=Role.PATIENT,
        )
        assert user.email == "user@example.com"

    def test_normalizes_email_domain(self) -> None:
        """Домен email приводится к нижнему регистру при сохранении."""
        user = User.objects.create_user(
            email="user@EXAMPLE.COM",
            password="Pass123!",
            first_name="Тест",
            last_name="Тестов",
            role=Role.PATIENT,
        )
        assert user.email == "user@example.com"

    def test_empty_email_raises_value_error(self) -> None:
        """Создание пользователя без email вызывает ValueError."""
        with pytest.raises(ValueError, match="Email обязателен"):
            User.objects.create_user(
                email="",
                password="Pass123!",
                first_name="Тест",
                last_name="Тестов",
                role=Role.PATIENT,
            )

    def test_password_is_hashed(self) -> None:
        """Пароль хранится в хэшированном виде, а не открытым текстом."""
        raw_password = "Pass123!"
        user = User.objects.create_user(
            email="hash@example.com",
            password=raw_password,
            first_name="Тест",
            last_name="Тестов",
            role=Role.PATIENT,
        )
        assert user.password != raw_password
        assert user.check_password(raw_password) is True

    def test_user_is_saved_to_database(self) -> None:
        """Созданный пользователь сохраняется в базе данных."""
        User.objects.create_user(
            email="saved@example.com",
            password="Pass123!",
            first_name="Тест",
            last_name="Тестов",
            role=Role.PATIENT,
        )
        assert User.objects.filter(email="saved@example.com").exists()

    def test_extra_fields_applied(self) -> None:
        """Дополнительные поля передаются в модель без изменений."""
        user = User.objects.create_user(
            email="extra@example.com",
            password="Pass123!",
            first_name="Тест",
            last_name="Тестов",
            role=Role.DOCTOR,
        )
        assert user.role == Role.DOCTOR


class TestCreateSuperuser:
    """Тесты метода create_superuser."""

    def test_superuser_has_required_flags(self) -> None:
        """Суперпользователь создаётся с is_staff=True, is_superuser=True, is_active=True."""
        user = User.objects.create_superuser(
            email="admin@example.com",
            password="AdminPass123!",
            first_name="Админ",
            last_name="Adminов",
            role=Role.DOCTOR,
        )
        assert user.is_staff is True
        assert user.is_superuser is True
        assert user.is_active is True

    def test_is_staff_false_raises_value_error(self) -> None:
        """Создание суперпользователя с is_staff=False вызывает ValueError."""
        with pytest.raises(ValueError, match="is_staff=True"):
            User.objects.create_superuser(
                email="badstaff@example.com",
                password="Pass123!",
                first_name="Тест",
                last_name="Тестов",
                role=Role.DOCTOR,
                is_staff=False,
            )

    def test_is_superuser_false_raises_value_error(self) -> None:
        """Создание суперпользователя с is_superuser=False вызывает ValueError."""
        with pytest.raises(ValueError, match="is_superuser=True"):
            User.objects.create_superuser(
                email="badsuper@example.com",
                password="Pass123!",
                first_name="Тест",
                last_name="Тестов",
                role=Role.DOCTOR,
                is_superuser=False,
            )
