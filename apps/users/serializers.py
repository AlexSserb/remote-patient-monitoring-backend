"""Сериализаторы для двухшаговой аутентификации."""

from __future__ import annotations

from typing import Any, ClassVar

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.diagnoses.models import Diagnosis
from apps.diagnoses.serializers import PatientDiagnosisSerializer
from apps.users.models import CaregiverPatient, DoctorPatient, Role
from apps.users.services import (
    blacklist_refresh_token,
    create_pre_auth_token,
    decode_pre_auth_token,
    generate_and_store_email_change_otp,
    generate_and_store_otp,
    issue_token_pair,
    rotate_refresh_token,
    send_email_change_otp,
    send_otp_email,
    verify_and_consume_email_change_otp,
    verify_and_consume_otp,
    verify_and_consume_password_reset_otp,
)

UserModel = get_user_model()


class LoginSerializer(serializers.Serializer):
    """Сериализатор первого шага: проверяет пароль, отправляет OTP, возвращает pre_auth_token."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs: dict[str, Any]) -> dict[str, str]:
        """Аутентифицирует пользователя, генерирует OTP и возвращает pre_auth_token."""
        user = authenticate(
            request=self.context.get("request"),
            email=attrs["email"],
            password=attrs["password"],
        )
        if user is None:
            msg = "Неверный email или пароль."
            raise serializers.ValidationError(msg, code="invalid_credentials")
        if not user.is_active:
            msg = "Учётная запись отключена."
            raise serializers.ValidationError(msg, code="inactive_user")

        otp = generate_and_store_otp(user.pk)
        send_otp_email(user.email, otp)

        return {"pre_auth_token": create_pre_auth_token(user.pk)}


class VerifyOTPSerializer(serializers.Serializer):
    """Сериализатор второго шага: проверяет OTP и выдаёт JWT-пару."""

    pre_auth_token = serializers.CharField()
    otp = serializers.CharField(min_length=6, max_length=6)

    def validate(self, attrs: dict[str, Any]) -> dict[str, str]:
        """Верифицирует pre_auth_token и OTP, возвращает access и refresh токены."""
        try:
            user_id = decode_pre_auth_token(attrs["pre_auth_token"])
        except ValueError as exc:
            raise serializers.ValidationError(str(exc), code="invalid_pre_auth_token") from exc

        if not verify_and_consume_otp(user_id, attrs["otp"]):
            msg = "Неверный или истёкший OTP-код."
            raise serializers.ValidationError(msg, code="invalid_otp")

        try:
            user = UserModel.objects.get(pk=user_id)
        except UserModel.DoesNotExist as exc:
            msg = "Пользователь не найден."
            raise serializers.ValidationError(msg, code="user_not_found") from exc

        return issue_token_pair(user)


class TokenRefreshSerializer(serializers.Serializer):
    """Сериализатор ротации токенов: инвалидирует старый refresh, выпускает новую пару."""

    refresh = serializers.CharField()

    def validate(self, attrs: dict[str, Any]) -> dict[str, str]:
        """Инвалидирует старый refresh-токен и возвращает новую JWT-пару."""
        try:
            return rotate_refresh_token(attrs["refresh"])
        except ValueError as exc:
            raise serializers.ValidationError(str(exc), code="invalid_refresh_token") from exc


class UserProfileSerializer(serializers.ModelSerializer):
    """Сериализатор профиля пользователя для отображения публичных данных."""

    class Meta:
        """Метаданные сериализатора профиля."""

        model = UserModel
        fields: ClassVar[list[str]] = ["id", "email", "first_name", "last_name", "role", "date_joined"]


class UpdateProfileSerializer(serializers.ModelSerializer):
    """Сериализатор обновления имени и фамилии пользователя."""

    class Meta:
        """Метаданные сериализатора обновления профиля."""

        model = UserModel
        fields: ClassVar[list[str]] = ["first_name", "last_name"]


class EmailChangeRequestSerializer(serializers.Serializer):
    """Сериализатор запроса на смену email: проверяет уникальность и отправляет OTP на новый адрес."""

    new_email = serializers.EmailField()

    def validate_new_email(self, value: str) -> str:
        """Проверяет, что новый email не занят другим пользователем."""
        if UserModel.objects.filter(email=value).exists():
            msg = "Пользователь с таким email уже существует."
            raise serializers.ValidationError(msg, code="email_taken")
        return value

    def save(self, **kwargs: Any) -> dict[str, str]:
        """Генерирует OTP и отправляет его на новый email; возвращает пустой словарь."""
        user: Any = kwargs["user"]
        new_email: str = self.validated_data["new_email"]
        otp = generate_and_store_email_change_otp(user.pk, new_email)
        send_email_change_otp(new_email, otp)
        return {}


class EmailChangeVerifySerializer(serializers.Serializer):
    """Сериализатор подтверждения смены email: проверяет OTP и применяет новый адрес."""

    otp = serializers.CharField(min_length=6, max_length=6)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Проверяет OTP и сохраняет новый email в validated_data для последующего применения."""
        user: Any = self.context["user"]
        new_email = verify_and_consume_email_change_otp(user.pk, attrs["otp"])
        if new_email is None:
            msg = "Неверный или истёкший код подтверждения."
            raise serializers.ValidationError(msg, code="invalid_otp")
        # Повторная проверка уникальности: другой пользователь мог занять адрес за время TTL
        if UserModel.objects.filter(email=new_email).exists():
            msg = "Пользователь с таким email уже существует."
            raise serializers.ValidationError(msg, code="email_taken")
        attrs["new_email"] = new_email
        return attrs


class PasswordResetVerifySerializer(serializers.Serializer):
    """Сериализатор подтверждения смены пароля: проверяет OTP и устанавливает новый пароль."""

    otp = serializers.CharField(min_length=6, max_length=6)
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_new_password(self, value: str) -> str:
        """Проверяет новый пароль через стандартные валидаторы Django."""
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Верифицирует OTP и возвращает атрибуты для последующей установки пароля."""
        user: Any = self.context["user"]
        if not verify_and_consume_password_reset_otp(user.pk, attrs["otp"]):
            msg = "Неверный или истёкший код подтверждения."
            raise serializers.ValidationError(msg, code="invalid_otp")
        return attrs


class LogoutSerializer(serializers.Serializer):
    """Сериализатор выхода из системы: добавляет refresh-токен в Redis-блэклист."""

    refresh = serializers.CharField()

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Помещает refresh-токен в чёрный список Redis."""
        try:
            blacklist_refresh_token(attrs["refresh"])
        except ValueError as exc:
            raise serializers.ValidationError(str(exc), code="invalid_refresh_token") from exc
        return attrs


class UserShortSerializer(serializers.ModelSerializer):
    """Краткое представление пользователя для списков фильтрации."""

    class Meta:
        """Метаданные сериализатора."""

        model = UserModel
        fields: ClassVar[list[str]] = ["id", "email", "first_name", "last_name"]


class PatientDoctorSerializer(serializers.ModelSerializer):
    """Доктор пациента с полями пользователя верхнего уровня для корректной генерации схемы."""

    id = serializers.IntegerField(source="doctor.id")
    email = serializers.EmailField(source="doctor.email")
    first_name = serializers.CharField(source="doctor.first_name")
    last_name = serializers.CharField(source="doctor.last_name")

    class Meta:
        """Метаданные сериализатора."""

        model = DoctorPatient
        fields: ClassVar[list[str]] = ["id", "email", "first_name", "last_name"]


class PatientCaregiverSerializer(serializers.ModelSerializer):
    """Опекун пациента с полями пользователя верхнего уровня для корректной генерации схемы."""

    id = serializers.IntegerField(source="caregiver.id")
    email = serializers.EmailField(source="caregiver.email")
    first_name = serializers.CharField(source="caregiver.first_name")
    last_name = serializers.CharField(source="caregiver.last_name")

    class Meta:
        """Метаданные сериализатора."""

        model = CaregiverPatient
        fields: ClassVar[list[str]] = ["id", "email", "first_name", "last_name"]


class EditPatientSerializer(serializers.Serializer):
    """Сериализатор редактирования пациента доктором: синхронизирует диагнозы и прикреплённых докторов."""

    diagnoses = serializers.ListField(child=serializers.IntegerField(), required=False)
    doctors = serializers.ListField(child=serializers.IntegerField(), required=False)

    def validate_diagnoses(self, value: list[int]) -> list[int]:
        """Проверяет, что все переданные идентификаторы диагнозов существуют в базе."""
        existing = set(Diagnosis.objects.filter(pk__in=value).values_list("pk", flat=True))
        missing = set(value) - existing
        if missing:
            msg = f"Diagnoses not found: {sorted(missing)}"
            raise serializers.ValidationError(msg)
        return value

    def validate_doctors(self, value: list[int]) -> list[int]:
        """Проверяет, что все переданные идентификаторы принадлежат пользователям с ролью доктора."""
        existing = set(UserModel.objects.filter(pk__in=value, role=Role.DOCTOR).values_list("pk", flat=True))
        missing = set(value) - existing
        if missing:
            msg = f"Doctors not found: {sorted(missing)}"
            raise serializers.ValidationError(msg)
        return value


class PatientListItemSerializer(serializers.ModelSerializer):
    """Сериализатор элемента списка пациентов: основные поля, опекуны, доктора и диагнозы."""

    # Поле заполняется аннотацией Count на уровне queryset
    caregiver_count = serializers.IntegerField()
    diagnoses = PatientDiagnosisSerializer(many=True)
    doctors = PatientDoctorSerializer(many=True, source="patient_doctors")
    caregivers = PatientCaregiverSerializer(many=True, source="patient_caregivers")

    class Meta:
        """Метаданные сериализатора."""

        model = UserModel
        fields: ClassVar[list[str]] = [
            "id",
            "email",
            "first_name",
            "last_name",
            "date_joined",
            "caregiver_count",
            "diagnoses",
            "doctors",
            "caregivers",
        ]
