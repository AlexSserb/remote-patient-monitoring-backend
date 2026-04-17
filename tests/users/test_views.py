"""Тесты API-эндпоинтов через APIClient."""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import CaregiverPatient, DoctorPatient, Role, User
from apps.users.services import (
    create_pre_auth_token,
    generate_and_store_email_change_otp,
    generate_and_store_otp,
    generate_and_store_password_reset_otp,
    issue_token_pair,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Аутентификация: вход
# ---------------------------------------------------------------------------


class TestLogin:
    """Тесты первого шага входа (email + пароль)."""

    def test_valid_credentials_return_200_and_pre_auth_token(
        self, api_client: APIClient, user: User, mailoutbox: list
    ) -> None:
        """Верные учётные данные возвращают pre_auth_token и отправляют OTP."""
        response = api_client.post(
            reverse("auth-login"),
            {"email": user.email, "password": "SecurePass123!"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert "pre_auth_token" in response.data
        assert len(mailoutbox) == 1

    def test_wrong_password_returns_400(self, api_client: APIClient, user: User) -> None:
        """Неверный пароль возвращает 400."""
        response = api_client.post(
            reverse("auth-login"),
            {"email": user.email, "password": "WrongPass!"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_nonexistent_user_returns_400(self, api_client: APIClient) -> None:
        """Несуществующий email возвращает 400."""
        response = api_client.post(
            reverse("auth-login"),
            {"email": "nobody@example.com", "password": "Pass123!"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Аутентификация: верификация OTP
# ---------------------------------------------------------------------------


class TestVerifyOtp:
    """Тесты второго шага входа — верификации OTP."""

    def test_valid_otp_returns_jwt_pair(self, api_client: APIClient, user: User) -> None:
        """Верный OTP возвращает access и refresh токены."""
        pre_auth_token = create_pre_auth_token(user.pk)
        otp = generate_and_store_otp(user.pk)
        response = api_client.post(
            reverse("auth-verify-otp"),
            {"pre_auth_token": pre_auth_token, "otp": otp},
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data

    def test_wrong_otp_returns_400(self, api_client: APIClient, user: User) -> None:
        """Неверный OTP возвращает 400."""
        pre_auth_token = create_pre_auth_token(user.pk)
        generate_and_store_otp(user.pk)
        response = api_client.post(
            reverse("auth-verify-otp"),
            {"pre_auth_token": pre_auth_token, "otp": "000000"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_pre_auth_token_returns_400(self, api_client: APIClient, user: User) -> None:
        """Невалидный pre_auth_token возвращает 400."""
        otp = generate_and_store_otp(user.pk)
        response = api_client.post(
            reverse("auth-verify-otp"),
            {"pre_auth_token": "bad.token", "otp": otp},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Аутентификация: обновление токена
# ---------------------------------------------------------------------------


class TestTokenRefresh:
    """Тесты ротации refresh-токена."""

    def test_valid_refresh_returns_new_pair(self, api_client: APIClient, user: User) -> None:
        """Валидный refresh-токен возвращает новую пару JWT."""
        tokens = issue_token_pair(user)
        response = api_client.post(
            reverse("auth-token-refresh"),
            {"refresh": tokens["refresh"]},
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data

    def test_reused_refresh_token_returns_400(self, api_client: APIClient, user: User) -> None:
        """Повторное использование refresh-токена возвращает 400 (блэклист)."""
        tokens = issue_token_pair(user)
        api_client.post(reverse("auth-token-refresh"), {"refresh": tokens["refresh"]})
        response = api_client.post(reverse("auth-token-refresh"), {"refresh": tokens["refresh"]})
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Аутентификация: выход
# ---------------------------------------------------------------------------


class TestLogout:
    """Тесты выхода из системы."""

    def test_logout_blacklists_token_and_returns_204(self, auth_client: APIClient, user: User) -> None:
        """Выход добавляет refresh-токен в блэклист и возвращает 204."""
        tokens = issue_token_pair(user)
        response = auth_client.post(reverse("auth-logout"), {"refresh": tokens["refresh"]})
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_logout_requires_authentication(self, api_client: APIClient, user: User) -> None:
        """Выход без токена аутентификации возвращает 401."""
        tokens = issue_token_pair(user)
        response = api_client.post(reverse("auth-logout"), {"refresh": tokens["refresh"]})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Профиль пользователя
# ---------------------------------------------------------------------------


class TestGetUser:
    """Тесты получения и обновления профиля."""

    def test_get_own_profile_returns_200(self, auth_client: APIClient, user: User) -> None:
        """Авторизованный пользователь получает свой профиль."""
        response = auth_client.get(reverse("users-profile", kwargs={"user_id": user.pk}))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == user.email

    def test_get_other_users_profile_returns_403(self, auth_client: APIClient, other_user: User) -> None:
        """Попытка получить чужой профиль возвращает 403."""
        response = auth_client.get(reverse("users-profile", kwargs={"user_id": other_user.pk}))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_get_returns_401(self, api_client: APIClient, user: User) -> None:
        """Запрос без токена возвращает 401."""
        response = api_client.get(reverse("users-profile", kwargs={"user_id": user.pk}))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_patch_own_profile_returns_200_with_updated_data(self, auth_client: APIClient, user: User) -> None:
        """Обновление собственного профиля возвращает 200 с изменёнными данными."""
        response = auth_client.patch(
            reverse("users-profile", kwargs={"user_id": user.pk}),
            {"first_name": "Алексей", "last_name": "Смирнов"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["first_name"] == "Алексей"
        assert response.data["last_name"] == "Смирнов"

    def test_patch_other_users_profile_returns_403(self, auth_client: APIClient, other_user: User) -> None:
        """Попытка изменить чужой профиль возвращает 403."""
        response = auth_client.patch(
            reverse("users-profile", kwargs={"user_id": other_user.pk}),
            {"first_name": "Хакер"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# Смена email
# ---------------------------------------------------------------------------


class TestEmailChange:
    """Тесты запроса и подтверждения смены email."""

    def test_request_email_change_returns_204(self, auth_client: APIClient, user: User, mailoutbox: list) -> None:
        """Запрос на смену email отправляет OTP и возвращает 204."""
        response = auth_client.post(
            reverse("email-change-request", kwargs={"user_id": user.pk}),
            {"new_email": "new@example.com"},
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert len(mailoutbox) == 1

    def test_request_email_change_for_other_user_returns_403(self, auth_client: APIClient, other_user: User) -> None:
        """Попытка сменить email другого пользователя возвращает 403."""
        response = auth_client.post(
            reverse("email-change-request", kwargs={"user_id": other_user.pk}),
            {"new_email": "hacked@example.com"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_verify_email_change_updates_email_and_returns_200(self, auth_client: APIClient, user: User) -> None:
        """Верный OTP меняет email пользователя и возвращает обновлённый профиль."""
        new_email = "verified@example.com"
        code = generate_and_store_email_change_otp(user.pk, new_email)
        response = auth_client.post(
            reverse("email-change-verify", kwargs={"user_id": user.pk}),
            {"otp": code},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == new_email
        user.refresh_from_db()
        assert user.email == new_email

    def test_verify_email_change_with_wrong_otp_returns_400(self, auth_client: APIClient, user: User) -> None:
        """Неверный OTP при верификации смены email возвращает 400."""
        generate_and_store_email_change_otp(user.pk, "verified@example.com")
        response = auth_client.post(
            reverse("email-change-verify", kwargs={"user_id": user.pk}),
            {"otp": "000000"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Смена пароля
# ---------------------------------------------------------------------------


class TestPasswordReset:
    """Тесты запроса и подтверждения смены пароля."""

    def test_request_password_reset_sends_otp_and_returns_204(
        self, auth_client: APIClient, user: User, mailoutbox: list
    ) -> None:
        """Запрос на смену пароля отправляет OTP и возвращает 204."""
        response = auth_client.post(reverse("password-reset-request", kwargs={"user_id": user.pk}))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert len(mailoutbox) == 1

    def test_request_password_reset_for_other_user_returns_403(self, auth_client: APIClient, other_user: User) -> None:
        """Попытка запросить сброс пароля другого пользователя возвращает 403."""
        response = auth_client.post(reverse("password-reset-request", kwargs={"user_id": other_user.pk}))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_verify_password_reset_updates_password_and_returns_204(self, auth_client: APIClient, user: User) -> None:
        """Верный OTP и новый пароль меняют пароль пользователя и возвращают 204."""
        new_password = "BrandNewPass789!"
        code = generate_and_store_password_reset_otp(user.pk)
        response = auth_client.post(
            reverse("password-reset-verify", kwargs={"user_id": user.pk}),
            {"otp": code, "new_password": new_password},
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        user.refresh_from_db()
        assert user.check_password(new_password) is True

    def test_verify_password_reset_with_wrong_otp_returns_400(self, auth_client: APIClient, user: User) -> None:
        """Неверный OTP при верификации смены пароля возвращает 400."""
        generate_and_store_password_reset_otp(user.pk)
        response = auth_client.post(
            reverse("password-reset-verify", kwargs={"user_id": user.pk}),
            {"otp": "000000", "new_password": "BrandNewPass789!"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Список пациентов
# ---------------------------------------------------------------------------


class TestListPatients:
    """Тесты эндпоинта списка пациентов для докторов и опекунов."""

    @pytest.fixture(autouse=True)
    def setup_users(self, db: None) -> None:
        """Создаёт доктора, второго доктора, опекуна и двух пациентов для тестов."""
        self.doctor = User.objects.create_user(
            email="doctor@example.com",
            password="Pass123!",
            first_name="Доктор",
            last_name="Докторов",
            role=Role.DOCTOR,
        )
        self.other_doctor = User.objects.create_user(
            email="doctor2@example.com",
            password="Pass123!",
            first_name="Другой",
            last_name="Доктор",
            role=Role.DOCTOR,
        )
        self.caregiver = User.objects.create_user(
            email="caregiver@example.com",
            password="Pass123!",
            first_name="Опекун",
            last_name="Опекунов",
            role=Role.CAREGIVER,
        )
        # patient1 прикреплён к doctor и caregiver
        self.patient1 = User.objects.create_user(
            email="patient1@example.com",
            password="Pass123!",
            first_name="Пациент",
            last_name="Первый",
            role=Role.PATIENT,
        )
        # patient2 прикреплён к doctor, без опекуна
        self.patient2 = User.objects.create_user(
            email="patient2@example.com",
            password="Pass123!",
            first_name="Пациент",
            last_name="Второй",
            role=Role.PATIENT,
        )
        # patient3 не прикреплён ни к одному доктору
        self.patient3 = User.objects.create_user(
            email="patient3@example.com",
            password="Pass123!",
            first_name="Пациент",
            last_name="Третий",
            role=Role.PATIENT,
        )

        DoctorPatient.objects.create(doctor=self.doctor, patient=self.patient1)
        DoctorPatient.objects.create(doctor=self.doctor, patient=self.patient2)
        CaregiverPatient.objects.create(caregiver=self.caregiver, patient=self.patient1)

    def _auth_client(self, user: User) -> APIClient:
        """Возвращает аутентифицированный клиент для заданного пользователя."""
        client = APIClient()
        tokens = issue_token_pair(user)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        return client

    def test_doctor_sees_all_patients_by_default(self) -> None:
        """Доктор по умолчанию видит всех пациентов системы."""
        response = self._auth_client(self.doctor).get(reverse("patients-list"))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3

    def test_doctor_attached_filter_returns_only_assigned_patients(self) -> None:
        """Фильтр attached=true возвращает только прикреплённых к доктору пациентов."""
        response = self._auth_client(self.doctor).get(reverse("patients-list"), {"attached": "true"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2
        ids = {r["id"] for r in response.data["results"]}
        assert ids == {self.patient1.pk, self.patient2.pk}

    def test_other_doctor_attached_filter_returns_empty(self) -> None:
        """Доктор без прикреплённых пациентов получает пустой список при attached=true."""
        response = self._auth_client(self.other_doctor).get(reverse("patients-list"), {"attached": "true"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0

    def test_caregiver_sees_only_attached_patients(self) -> None:
        """Опекун видит только своих прикреплённых пациентов."""
        response = self._auth_client(self.caregiver).get(reverse("patients-list"))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == self.patient1.pk

    def test_caregiver_attached_param_is_ignored(self) -> None:
        """Параметр attached не влияет на результат для опекуна."""
        response_default = self._auth_client(self.caregiver).get(reverse("patients-list"))
        response_attached = self._auth_client(self.caregiver).get(reverse("patients-list"), {"attached": "true"})
        assert response_default.data["count"] == response_attached.data["count"]

    def test_has_caregiver_yes_filter(self) -> None:
        """Фильтр has_caregiver=yes возвращает только пациентов с опекуном."""
        response = self._auth_client(self.doctor).get(reverse("patients-list"), {"has_caregiver": "yes"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == self.patient1.pk

    def test_has_caregiver_no_filter(self) -> None:
        """Фильтр has_caregiver=no возвращает только пациентов без опекуна."""
        response = self._auth_client(self.doctor).get(reverse("patients-list"), {"has_caregiver": "no"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2
        ids = {r["id"] for r in response.data["results"]}
        assert ids == {self.patient2.pk, self.patient3.pk}

    def test_caregiver_count_field_is_correct(self) -> None:
        """Поле caregiver_count отражает реальное количество опекунов пациента."""
        response = self._auth_client(self.doctor).get(reverse("patients-list"))
        assert response.status_code == status.HTTP_200_OK
        results_by_id = {r["id"]: r for r in response.data["results"]}
        assert results_by_id[self.patient1.pk]["caregiver_count"] == 1
        assert results_by_id[self.patient2.pk]["caregiver_count"] == 0
        assert results_by_id[self.patient3.pk]["caregiver_count"] == 0

    def test_pagination_page_size(self) -> None:
        """Параметр page_size ограничивает количество результатов в ответе."""
        response = self._auth_client(self.doctor).get(reverse("patients-list"), {"page_size": "1"})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["count"] == 3

    def test_pagination_second_page(self) -> None:
        """Вторая страница возвращает следующий срез результатов."""
        response = self._auth_client(self.doctor).get(reverse("patients-list"), {"page": "2", "page_size": "2"})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1

    def test_response_contains_expected_fields(self) -> None:
        """Ответ содержит все обязательные поля пациента."""
        response = self._auth_client(self.doctor).get(reverse("patients-list"), {"attached": "true"})
        assert response.status_code == status.HTTP_200_OK
        item = response.data["results"][0]
        assert {"id", "email", "first_name", "last_name", "date_joined", "caregiver_count"} <= item.keys()

    def test_patient_cannot_access_endpoint(self) -> None:
        """Пациент не имеет доступа к списку пациентов."""
        response = self._auth_client(self.patient1).get(reverse("patients-list"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_request_returns_401(self, api_client: APIClient) -> None:
        """Неаутентифицированный запрос возвращает 401."""
        response = api_client.get(reverse("patients-list"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
