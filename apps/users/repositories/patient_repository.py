"""Репозиторий операций с пациентами."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.contrib.auth import get_user_model
from django.db.models import Count, Q

from apps.diagnoses.models import PatientDiagnosis
from apps.users.models import DoctorPatient, Role

if TYPE_CHECKING:
    from django.db.models import QuerySet

UserModel = get_user_model()


class PatientRepository:
    """Репозиторий операций с пациентами, докторами и опекунами."""

    def get_patient_by_id(self, patient_id: int) -> Any:
        """Возвращает пользователя с ролью пациента или бросает DoesNotExist."""
        return UserModel.objects.get(pk=patient_id, role=Role.PATIENT)

    def has_doctor_access(self, doctor: Any, patient: Any) -> bool:
        """Проверяет наличие связи доктор-пациент в базе данных."""
        return DoctorPatient.objects.filter(doctor=doctor, patient=patient).exists()

    def apply_role_filter(self, qs: QuerySet, user: Any, *, attached: bool = False) -> QuerySet:
        """Фильтрует пациентов по роли пользователя: доктор видит всех или прикреплённых, опекун — своих."""
        if user.role == Role.DOCTOR:
            if attached:
                qs = qs.filter(patient_doctors__doctor=user)
        else:
            # Опекун видит только своих пациентов
            qs = qs.filter(patient_caregivers__caregiver=user)
        return qs

    def apply_filters(  # noqa: PLR0913
        self,
        qs: QuerySet,
        *,
        has_caregiver: str = "all",
        doctor_ids: list[str] | None = None,
        caregiver_ids: list[str] | None = None,
        diagnosis_ids: list[str] | None = None,
        search: str = "",
    ) -> QuerySet:
        """Применяет поисковые и фильтрационные параметры к QuerySet пациентов."""
        if has_caregiver == "yes":
            qs = qs.filter(caregiver_count__gt=0)
        elif has_caregiver == "no":
            qs = qs.filter(caregiver_count=0)

        if doctor_ids:
            qs = qs.filter(patient_doctors__doctor__in=doctor_ids)
        if caregiver_ids:
            qs = qs.filter(patient_caregivers__caregiver__in=caregiver_ids)
        if diagnosis_ids:
            qs = qs.filter(diagnoses__diagnosis__in=diagnosis_ids)
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search) | Q(last_name__icontains=search) | Q(email__icontains=search)
            )

        # JOIN-фильтры по спискам могут дублировать строки
        return qs.distinct()

    def sync_diagnoses(self, patient: Any, diagnosis_ids: list[int], assigned_by: Any) -> None:
        """Синхронизирует диагнозы пациента: добавляет новые и удаляет отсутствующие в переданном списке."""
        current_ids = set(PatientDiagnosis.objects.filter(patient=patient).values_list("diagnosis_id", flat=True))
        new_ids = set(diagnosis_ids)
        if to_remove := current_ids - new_ids:
            PatientDiagnosis.objects.filter(patient=patient, diagnosis_id__in=to_remove).delete()
        if to_add := new_ids - current_ids:
            PatientDiagnosis.objects.bulk_create(
                [PatientDiagnosis(patient=patient, diagnosis_id=did, assigned_by=assigned_by) for did in to_add]
            )

    def sync_doctors(self, patient: Any, doctor_ids: list[int]) -> None:
        """Синхронизирует список докторов пациента: добавляет новых и удаляет отсутствующих в переданном списке."""
        current_ids = set(DoctorPatient.objects.filter(patient=patient).values_list("doctor_id", flat=True))
        new_ids = set(doctor_ids)
        if to_remove := current_ids - new_ids:
            DoctorPatient.objects.filter(patient=patient, doctor_id__in=to_remove).delete()
        if to_add := new_ids - current_ids:
            DoctorPatient.objects.bulk_create([DoctorPatient(patient=patient, doctor_id=did) for did in to_add])

    def get_with_details(self, patient_id: int) -> Any:
        """Возвращает пациента с предзагруженными связями и аннотацией количества опекунов."""
        return (
            UserModel.objects.filter(pk=patient_id)
            .prefetch_related("diagnoses__diagnosis", "patient_doctors__doctor", "patient_caregivers__caregiver")
            .annotate(caregiver_count=Count("patient_caregivers", distinct=True))
            .get()
        )
