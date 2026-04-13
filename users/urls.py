"""URL-маршруты аутентификации."""

from __future__ import annotations

from django.urls import path

from users.views import (
    get_user,
    login,
    logout,
    request_email_change,
    request_password_reset,
    token_refresh,
    verify_email_change,
    verify_otp,
    verify_password_reset,
)

urlpatterns = [
    path("auth/login/", login, name="auth-login"),
    path("auth/verify-otp/", verify_otp, name="auth-verify-otp"),
    path("auth/token/refresh/", token_refresh, name="auth-token-refresh"),
    path("auth/logout/", logout, name="auth-logout"),
    path("<int:user_id>/", get_user, name="users-profile"),
    path("<int:user_id>/email-change/", request_email_change, name="email-change-request"),
    path("<int:user_id>/email-change/verify/", verify_email_change, name="email-change-verify"),
    path("<int:user_id>/password-reset/", request_password_reset, name="password-reset-request"),
    path("<int:user_id>/password-reset/verify/", verify_password_reset, name="password-reset-verify"),
]
