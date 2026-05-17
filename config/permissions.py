"""Общие классы прав доступа для переиспользования во всех приложениях."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework.permissions import BasePermission

from apps.users.models import Role

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.views import APIView


class IsDoctorOrCaregiver(BasePermission):
    """Разрешает доступ только пользователям с ролью доктора или опекуна."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        """Возвращает True, если у пользователя роль доктора или опекуна."""
        return hasattr(request.user, "role") and request.user.role in (Role.DOCTOR, Role.CAREGIVER)
