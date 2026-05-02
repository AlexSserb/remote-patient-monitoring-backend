"""URL-маршруты приложения diagnoses."""

from __future__ import annotations

from django.urls import path

from apps.diagnoses.views import DiaryEntryViewSet, get_analytics, list_diagnoses, list_diary_fields

diary_entry_list = DiaryEntryViewSet.as_view({"get": "list", "post": "create"})
diary_entry_detail = DiaryEntryViewSet.as_view({"patch": "partial_update", "delete": "destroy"})

urlpatterns = [
    path("", list_diagnoses, name="diagnoses-list"),
    path("analytics/", get_analytics, name="diagnoses-analytics"),
    path("diary-fields/", list_diary_fields, name="diagnoses-diary-fields"),
    path("diary-entries/", diary_entry_list, name="diary-entries-list"),
    path("diary-entries/<int:pk>/", diary_entry_detail, name="diary-entries-detail"),
]
