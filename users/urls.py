"""URL-маршруты аутентификации."""

from __future__ import annotations

from django.urls import path

from users.views import get_user, login, logout, request_email_change, token_refresh, verify_email_change, verify_otp

urlpatterns = [
    path("auth/login/", login, name="auth-login"),
    path("auth/verify-otp/", verify_otp, name="auth-verify-otp"),
    path("auth/token/refresh/", token_refresh, name="auth-token-refresh"),
    path("auth/logout/", logout, name="auth-logout"),
    path("<int:user_id>/", get_user, name="users-profile"),
    path("<int:user_id>/email-change/", request_email_change, name="email-change-request"),
    path("<int:user_id>/email-change/verify/", verify_email_change, name="email-change-verify"),
]
