"""URL-маршруты приложения notifications."""

from __future__ import annotations

from django.urls import path

from apps.notifications.views import schedule_detail, schedules_list_create

urlpatterns = [
    path("schedules/", schedules_list_create, name="notification-schedules"),
    path("schedules/<int:schedule_id>/", schedule_detail, name="notification-schedule-detail"),
]
