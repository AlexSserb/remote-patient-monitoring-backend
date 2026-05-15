"""URL-маршруты приложения notifications."""

from __future__ import annotations

from django.urls import path

from apps.notifications.views import (
    email_subscription,
    push_subscription,
    schedule_detail,
    schedules_list_create,
    vapid_public_key,
)

urlpatterns = [
    path("schedules/", schedules_list_create, name="notification-schedules"),
    path("schedules/<int:schedule_id>/", schedule_detail, name="notification-schedule-detail"),
    path("vapid-public-key/", vapid_public_key, name="notification-vapid-public-key"),
    path("push-subscription/", push_subscription, name="notification-push-subscription"),
    path("email-subscription/", email_subscription, name="notification-email-subscription"),
]
