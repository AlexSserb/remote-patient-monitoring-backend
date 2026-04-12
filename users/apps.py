"""Конфигурация приложения пользователей."""

from __future__ import annotations

from django.apps import AppConfig


class UsersConfig(AppConfig):
    """Конфигурация приложения users — кастомная модель пользователя и аутентификация."""

    name = "users"
