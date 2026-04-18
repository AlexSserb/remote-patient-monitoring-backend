"""URL-маршруты приложения diagnoses."""

from __future__ import annotations

from django.urls import path

from apps.diagnoses.views import list_diagnoses

urlpatterns = [
    path("", list_diagnoses, name="diagnoses-list"),
]
