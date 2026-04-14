"""Общие фикстуры для всей тестовой среды."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.users.models import Role, User
from apps.users.services import issue_token_pair

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(autouse=True)
def clear_cache() -> Generator[None, None, None]:
    """Очищает кэш до и после каждого теста для полной изоляции состояния."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client() -> APIClient:
    """Возвращает неаутентифицированный DRF API-клиент."""
    return APIClient()


@pytest.fixture
def user_data() -> dict[str, str]:
    """Возвращает базовый набор полей для создания тестового пользователя."""
    return {
        "email": "patient@example.com",
        "password": "SecurePass123!",
        "first_name": "Иван",
        "last_name": "Иванов",
        "role": Role.PATIENT,
    }


@pytest.fixture
def user(db: None, user_data: dict[str, str]) -> User:
    """Создаёт и возвращает тестового пользователя в базе данных."""
    return User.objects.create_user(**user_data)


@pytest.fixture
def auth_client(api_client: APIClient, user: User) -> APIClient:
    """Возвращает API-клиент с валидным JWT-токеном тестового пользователя."""
    tokens = issue_token_pair(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return api_client


@pytest.fixture
def other_user(db: None) -> User:
    """Создаёт второго тестового пользователя для проверки разграничения доступа."""
    return User.objects.create_user(
        email="other@example.com",
        password="SecurePass123!",
        first_name="Пётр",
        last_name="Петров",
        role=Role.DOCTOR,
    )
