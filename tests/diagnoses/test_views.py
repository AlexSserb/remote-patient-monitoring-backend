"""Тесты API-эндпоинтов модуля diagnoses: поля дневника и записи дневника."""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.diagnoses.models import DiagnosisMetric, DiaryEntry, DiaryEntryValue, Metric
from apps.users.models import User

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# GET /api/diagnoses/diary-fields/ — поля дневника
# ---------------------------------------------------------------------------


class TestListDiaryFields:
    """Тесты эндпоинта получения полей дневника пациента."""

    URL = "diagnoses-diary-fields"

    def test_unauthenticated_returns_401(self, api_client: APIClient) -> None:
        """Неаутентифицированный запрос возвращает 401."""
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_doctor_returns_403(self, doctor_client: APIClient) -> None:
        """Доктор получает 403 — у него нет дневника."""
        response = doctor_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_patient_without_diagnoses_returns_empty_list(self, patient_client: APIClient) -> None:
        """Пациент без диагнозов получает пустой список полей."""
        response = patient_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_patient_gets_fields_from_assigned_diagnosis(
        self,
        patient_client: APIClient,
        patient_diagnosis: None,
        dm_number: DiagnosisMetric,
        dm_boolean: DiagnosisMetric,
    ) -> None:
        """Пациент получает поля, соответствующие метрикам его диагнозов."""
        response = patient_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_200_OK
        codes = {f["code"] for f in response.data}
        assert codes == {"glucose", "insulin_taken"}

    def test_required_field_aggregation(
        self,
        patient_client: APIClient,
        patient_diagnosis: None,
        dm_number: DiagnosisMetric,
    ) -> None:
        """Поле отмечено как обязательное, если оно обязательно хотя бы в одном диагнозе."""
        response = patient_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_200_OK
        glucose = next(f for f in response.data if f["code"] == "glucose")
        assert glucose["is_required"] is True
        assert glucose["min_value"] == pytest.approx(3.9)
        assert glucose["max_value"] == pytest.approx(10.0)

    def test_caregiver_gets_fields_for_assigned_patient(
        self,
        caregiver_client: APIClient,
        patient: User,
        caregiver_patient_link: None,
        patient_diagnosis: None,
        dm_number: DiagnosisMetric,
    ) -> None:
        """Опекун получает поля дневника своего пациента по patient_id."""
        response = caregiver_client.get(reverse(self.URL), {"patient_id": patient.pk})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["code"] == "glucose"

    def test_caregiver_without_patient_id_returns_400(self, caregiver_client: APIClient) -> None:
        """Опекун без patient_id получает 400."""
        response = caregiver_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_caregiver_for_unassigned_patient_returns_403(
        self,
        caregiver_client: APIClient,
        patient: User,
    ) -> None:
        """Опекун без связи с пациентом получает 403."""
        response = caregiver_client.get(reverse(self.URL), {"patient_id": patient.pk})
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# GET /api/diagnoses/diary-entries/ — список записей дневника
# ---------------------------------------------------------------------------


class TestListDiaryEntries:
    """Тесты эндпоинта получения списка записей дневника."""

    URL = "diary-entries-list"

    def test_unauthenticated_returns_401(self, api_client: APIClient) -> None:
        """Неаутентифицированный запрос возвращает 401."""
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_doctor_returns_403(self, doctor_client: APIClient) -> None:
        """Доктор получает 403."""
        response = doctor_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_patient_gets_empty_list_initially(self, patient_client: APIClient) -> None:
        """Пациент без записей получает пустой список."""
        response = patient_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_patient_sees_own_entries(
        self,
        patient_client: APIClient,
        diary_entry_with_values: DiaryEntry,
    ) -> None:
        """Пациент видит свои записи с вложенными значениями метрик."""
        response = patient_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        entry = response.data[0]
        assert entry["id"] == diary_entry_with_values.pk
        assert len(entry["values"]) == 2

    def test_patient_does_not_see_other_patients_entries(
        self,
        patient_client: APIClient,
        patient2: User,
    ) -> None:
        """Пациент не видит записи другого пациента."""
        DiaryEntry.objects.create(patient=patient2)
        response = patient_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_caregiver_gets_patient_entries(
        self,
        caregiver_client: APIClient,
        patient: User,
        caregiver_patient_link: None,
        diary_entry_with_values: DiaryEntry,
    ) -> None:
        """Опекун получает записи своего пациента через patient_id."""
        response = caregiver_client.get(reverse(self.URL), {"patient_id": patient.pk})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_caregiver_without_patient_id_returns_400(self, caregiver_client: APIClient) -> None:
        """Опекун без patient_id получает 400."""
        response = caregiver_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_caregiver_for_unassigned_patient_returns_403(
        self,
        caregiver_client: APIClient,
        patient: User,
    ) -> None:
        """Опекун без связи с пациентом получает 403."""
        response = caregiver_client.get(reverse(self.URL), {"patient_id": patient.pk})
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# POST /api/diagnoses/diary-entries/ — создание записи дневника
# ---------------------------------------------------------------------------


class TestCreateDiaryEntry:
    """Тесты эндпоинта создания записи дневника."""

    URL = "diary-entries-list"

    def test_unauthenticated_returns_401(self, api_client: APIClient) -> None:
        """Неаутентифицированный запрос возвращает 401."""
        response = api_client.post(reverse(self.URL), {"values": []}, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_doctor_returns_403(self, doctor_client: APIClient) -> None:
        """Доктор не может создавать записи дневника."""
        response = doctor_client.post(reverse(self.URL), {"values": []}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_patient_creates_entry_with_number_value(
        self,
        patient_client: APIClient,
        metric_number: Metric,
    ) -> None:
        """Пациент создаёт запись с числовым значением метрики."""
        payload = {"values": [{"metric_id": metric_number.pk, "value_number": 6.2}]}
        response = patient_client.post(reverse(self.URL), payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["values"][0]["value_number"] == pytest.approx(6.2)
        assert response.data["values"][0]["metric_code"] == "glucose"

    def test_patient_creates_entry_with_boolean_value(
        self,
        patient_client: APIClient,
        metric_boolean: Metric,
    ) -> None:
        """Пациент создаёт запись с булевым значением метрики."""
        payload = {"values": [{"metric_id": metric_boolean.pk, "value_boolean": True}]}
        response = patient_client.post(reverse(self.URL), payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["values"][0]["value_boolean"] is True

    def test_patient_creates_entry_with_text_value(
        self,
        patient_client: APIClient,
        metric_text: Metric,
    ) -> None:
        """Пациент создаёт запись с текстовым значением метрики."""
        payload = {"values": [{"metric_id": metric_text.pk, "value_text": "Чувствую себя хорошо"}]}
        response = patient_client.post(reverse(self.URL), payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["values"][0]["value_text"] == "Чувствую себя хорошо"

    def test_patient_creates_entry_with_multiple_values(
        self,
        patient_client: APIClient,
        metric_number: Metric,
        metric_boolean: Metric,
        metric_text: Metric,
    ) -> None:
        """Пациент создаёт запись с несколькими метриками одновременно."""
        payload = {
            "values": [
                {"metric_id": metric_number.pk, "value_number": 5.5},
                {"metric_id": metric_boolean.pk, "value_boolean": False},
                {"metric_id": metric_text.pk, "value_text": "Норма"},
            ]
        }
        response = patient_client.post(reverse(self.URL), payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data["values"]) == 3
        assert DiaryEntry.objects.count() == 1
        assert DiaryEntryValue.objects.count() == 3

    def test_caregiver_creates_entry_for_assigned_patient(
        self,
        caregiver_client: APIClient,
        patient: User,
        caregiver_patient_link: None,
        metric_number: Metric,
    ) -> None:
        """Опекун создаёт запись для своего пациента, передавая patient_id в query."""
        payload = {"values": [{"metric_id": metric_number.pk, "value_number": 7.1}]}
        response = caregiver_client.post(
            reverse(self.URL) + f"?patient_id={patient.pk}",
            payload,
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert DiaryEntry.objects.filter(patient=patient).count() == 1

    def test_caregiver_cannot_create_entry_for_unassigned_patient(
        self,
        caregiver_client: APIClient,
        patient: User,
        metric_number: Metric,
    ) -> None:
        """Опекун без связи с пациентом получает 403 при попытке создать запись."""
        payload = {"values": [{"metric_id": metric_number.pk, "value_number": 7.1}]}
        response = caregiver_client.post(
            reverse(self.URL) + f"?patient_id={patient.pk}",
            payload,
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_empty_values_list_is_accepted(self, patient_client: APIClient) -> None:
        """Запись с пустым списком значений принимается — пациент мог ничего не заполнить."""
        response = patient_client.post(reverse(self.URL), {"values": []}, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert DiaryEntry.objects.count() == 1


# ---------------------------------------------------------------------------
# PATCH /api/diagnoses/diary-entries/<pk>/ — обновление записи дневника
# ---------------------------------------------------------------------------


class TestUpdateDiaryEntry:
    """Тесты эндпоинта обновления записи дневника."""

    URL = "diary-entries-detail"

    def test_patient_updates_own_entry(
        self,
        patient_client: APIClient,
        diary_entry: DiaryEntry,
        metric_number: Metric,
    ) -> None:
        """Пациент обновляет значение метрики в своей записи."""
        DiaryEntryValue.objects.create(entry=diary_entry, metric=metric_number, value_number=5.0)
        payload = {"values": [{"metric_id": metric_number.pk, "value_number": 8.3}]}
        response = patient_client.patch(reverse(self.URL, args=[diary_entry.pk]), payload, format="json")
        assert response.status_code == status.HTTP_200_OK
        updated = DiaryEntryValue.objects.get(entry=diary_entry, metric=metric_number)
        assert updated.value_number == pytest.approx(8.3)

    def test_patient_cannot_update_other_patients_entry(
        self,
        patient_client: APIClient,
        patient2: User,
        metric_number: Metric,
    ) -> None:
        """Пациент не может редактировать чужую запись."""
        other_entry = DiaryEntry.objects.create(patient=patient2)
        payload = {"values": [{"metric_id": metric_number.pk, "value_number": 8.3}]}
        response = patient_client.patch(reverse(self.URL, args=[other_entry.pk]), payload, format="json")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_adds_new_metric_value(
        self,
        patient_client: APIClient,
        diary_entry: DiaryEntry,
        metric_number: Metric,
        metric_text: Metric,
    ) -> None:
        """PATCH добавляет новую метрику через upsert, если она отсутствовала."""
        DiaryEntryValue.objects.create(entry=diary_entry, metric=metric_number, value_number=5.0)
        payload = {
            "values": [
                {"metric_id": metric_number.pk, "value_number": 6.0},
                {"metric_id": metric_text.pk, "value_text": "Добавлено"},
            ]
        }
        response = patient_client.patch(reverse(self.URL, args=[diary_entry.pk]), payload, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert DiaryEntryValue.objects.filter(entry=diary_entry).count() == 2

    def test_caregiver_updates_assigned_patient_entry(
        self,
        caregiver_client: APIClient,
        patient: User,
        caregiver_patient_link: None,
        diary_entry: DiaryEntry,
        metric_number: Metric,
    ) -> None:
        """Опекун обновляет запись своего пациента."""
        DiaryEntryValue.objects.create(entry=diary_entry, metric=metric_number, value_number=5.0)
        payload = {"values": [{"metric_id": metric_number.pk, "value_number": 9.9}]}
        url = reverse(self.URL, args=[diary_entry.pk]) + f"?patient_id={patient.pk}"
        response = caregiver_client.patch(url, payload, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert DiaryEntryValue.objects.get(entry=diary_entry, metric=metric_number).value_number == pytest.approx(9.9)

    def test_caregiver_cannot_update_unassigned_patient_entry(
        self,
        caregiver_client: APIClient,
        patient: User,
        diary_entry: DiaryEntry,
        metric_number: Metric,
    ) -> None:
        """Опекун без связи не может редактировать записи пациента."""
        payload = {"values": [{"metric_id": metric_number.pk, "value_number": 9.9}]}
        url = reverse(self.URL, args=[diary_entry.pk]) + f"?patient_id={patient.pk}"
        response = caregiver_client.patch(url, payload, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_nonexistent_entry_returns_404(
        self,
        patient_client: APIClient,
        metric_number: Metric,
    ) -> None:
        """Запрос к несуществующей записи возвращает 404."""
        payload = {"values": [{"metric_id": metric_number.pk, "value_number": 5.0}]}
        response = patient_client.patch(reverse(self.URL, args=[99999]), payload, format="json")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# DELETE /api/diagnoses/diary-entries/<pk>/ — удаление записи дневника
# ---------------------------------------------------------------------------


class TestDeleteDiaryEntry:
    """Тесты эндпоинта удаления записи дневника."""

    URL = "diary-entries-detail"

    def test_patient_deletes_own_entry(
        self,
        patient_client: APIClient,
        diary_entry: DiaryEntry,
    ) -> None:
        """Пациент удаляет свою запись, получая 204."""
        response = patient_client.delete(reverse(self.URL, args=[diary_entry.pk]))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not DiaryEntry.objects.filter(pk=diary_entry.pk).exists()

    def test_delete_cascades_to_values(
        self,
        patient_client: APIClient,
        diary_entry_with_values: DiaryEntry,
    ) -> None:
        """Удаление записи каскадно удаляет все её значения метрик."""
        entry_pk = diary_entry_with_values.pk
        response = patient_client.delete(reverse(self.URL, args=[entry_pk]))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not DiaryEntryValue.objects.filter(entry_id=entry_pk).exists()

    def test_patient_cannot_delete_other_patients_entry(
        self,
        patient_client: APIClient,
        patient2: User,
    ) -> None:
        """Пациент не может удалить чужую запись."""
        other_entry = DiaryEntry.objects.create(patient=patient2)
        response = patient_client.delete(reverse(self.URL, args=[other_entry.pk]))
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert DiaryEntry.objects.filter(pk=other_entry.pk).exists()

    def test_caregiver_deletes_assigned_patient_entry(
        self,
        caregiver_client: APIClient,
        patient: User,
        caregiver_patient_link: None,
        diary_entry: DiaryEntry,
    ) -> None:
        """Опекун удаляет запись своего пациента."""
        url = reverse(self.URL, args=[diary_entry.pk]) + f"?patient_id={patient.pk}"
        response = caregiver_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not DiaryEntry.objects.filter(pk=diary_entry.pk).exists()

    def test_caregiver_cannot_delete_unassigned_patient_entry(
        self,
        caregiver_client: APIClient,
        patient: User,
        diary_entry: DiaryEntry,
    ) -> None:
        """Опекун без связи с пациентом получает 403."""
        url = reverse(self.URL, args=[diary_entry.pk]) + f"?patient_id={patient.pk}"
        response = caregiver_client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert DiaryEntry.objects.filter(pk=diary_entry.pk).exists()

    def test_unauthenticated_returns_401(self, api_client: APIClient, diary_entry: DiaryEntry) -> None:
        """Неаутентифицированный запрос возвращает 401."""
        response = api_client.delete(reverse(self.URL, args=[diary_entry.pk]))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_doctor_returns_403(self, doctor_client: APIClient, diary_entry: DiaryEntry) -> None:
        """Доктор получает 403 при попытке удалить запись дневника."""
        response = doctor_client.delete(reverse(self.URL, args=[diary_entry.pk]))
        assert response.status_code == status.HTTP_403_FORBIDDEN
