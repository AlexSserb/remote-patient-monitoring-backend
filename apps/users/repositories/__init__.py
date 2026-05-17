"""Репозитории приложения пользователей."""

from apps.users.repositories.patient_repository import PatientRepository
from apps.users.repositories.user_repository import UserRepository

__all__ = ["PatientRepository", "UserRepository"]
