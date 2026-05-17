"""Сервис управления пациентами."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from rest_framework.exceptions import PermissionDenied

from apps.users.repositories import PatientRepository, UserRepository


class PatientService:
    """Управление списком пациентов и редактированием данных пациента доктором."""

    def __init__(
        self,
        repo: PatientRepository | None = None,
        user_repo: UserRepository | None = None,
    ) -> None:
        """Инициализирует сервис с переданными или дефолтными репозиториями."""
        self._repo = repo or PatientRepository()
        self._user_repo = user_repo or UserRepository()

    def list_patients(self, user: Any, query_params: Any) -> tuple[Any, int]:
        """Возвращает страницу пациентов и общее число записей для переданных параметров запроса."""
        qs = self._user_repo.get_patients_base_qs()
        attached = query_params.get("attached", "false").lower() == "true"
        qs = self._repo.apply_role_filter(qs, user, attached=attached)
        qs = self._repo.apply_filters(
            qs,
            has_caregiver=query_params.get("has_caregiver", "all"),
            doctor_ids=query_params.getlist("doctors"),
            caregiver_ids=query_params.getlist("caregivers"),
            diagnosis_ids=query_params.getlist("diagnoses"),
            search=query_params.get("search", "").strip(),
        )
        total = qs.count()
        try:
            page = max(1, int(query_params.get("page", 1)))
            page_size = min(100, max(1, int(query_params.get("page_size", 20))))
        except ValueError:
            page, page_size = 1, 20
        start = (page - 1) * page_size
        return qs.order_by("last_name", "first_name")[start : start + page_size], total

    def edit_patient(self, doctor: Any, patient_id: int, data: dict) -> Any:
        """Обновляет диагнозы и список докторов пациента с проверкой доступа доктора."""
        try:
            patient = self._repo.get_patient_by_id(patient_id)
        except ObjectDoesNotExist as e:
            raise Http404 from e
        if not self._repo.has_doctor_access(doctor, patient):
            raise PermissionDenied
        if "diagnoses" in data:
            self._repo.sync_diagnoses(patient, data["diagnoses"], assigned_by=doctor)
        if "doctors" in data:
            self._repo.sync_doctors(patient, data["doctors"])
        return self._repo.get_with_details(patient.pk)
