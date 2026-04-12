"""Настройки Django для проекта remote-patient-monitoring."""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ["SECRET_KEY"]

DEBUG = os.getenv("DEBUG", "True") == "True"

ALLOWED_HOSTS: list[str] = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Сторонние
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    # Внутренние
    "users",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # CorsMiddleware должен идти до SessionMiddleware
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "monitoring.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "monitoring.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["PG_DATABASE"],
        "USER": os.environ["PG_LOGIN"],
        "PASSWORD": os.environ["PG_PASSWORD"],
        "HOST": os.environ["PG_HOST"],
        "PORT": os.getenv("PG_PORT", "5432"),
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "users.User"

REDIS_URL: str = os.environ["REDIS_URL"]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    # Ротация реализована вручную через Redis-блэклист, без хранения в PostgreSQL
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "TOKEN_TYPE_CLAIM": "token_type",
    "JTI_CLAIM": "jti",
}

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ["MAIL_SERVER"]
EMAIL_PORT = int(os.environ["MAIL_PORT"])
EMAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "False") == "True"
EMAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True") == "True"
EMAIL_HOST_USER = os.environ["MAIL_USERNAME"]
EMAIL_HOST_PASSWORD = os.environ["MAIL_PASSWORD"]
DEFAULT_FROM_EMAIL = os.environ["MAIL_DEFAULT_SENDER"]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

SPECTACULAR_SETTINGS = {
    "TITLE": "Remote Patient Monitoring API",
    "DESCRIPTION": "API для системы дистанционного мониторинга пациентов с эндокринными заболеваниями.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}
