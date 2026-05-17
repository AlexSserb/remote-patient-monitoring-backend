"""Настройки Django для тестовой среды."""

from __future__ import annotations

import os

from dotenv import load_dotenv

# Загружаем .env до import основных настроек, чтобы setdefault не перебил реальные значения
load_dotenv()

# Значения по умолчанию только для переменных, которые в реальном .env могут отсутствовать
# (например, в CI без .env-файла); DB-реквизиты берутся из .env или переменных среды CI
os.environ.setdefault("SECRET_KEY", "test-secret-key-do-not-use-in-production")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("MAIL_SERVER", "localhost")
os.environ.setdefault("MAIL_PORT", "25")
os.environ.setdefault("MAIL_USE_TLS", "False")
os.environ.setdefault("MAIL_USERNAME", "test@test.com")
os.environ.setdefault("MAIL_PASSWORD", "test")
os.environ.setdefault("MAIL_DEFAULT_SENDER", "test@test.com")
os.environ.setdefault("VAPID_PRIVATE_KEY", "MHQCAQEEIBkg4PNMM0m8aFjrGxPOqJgxAoGCCqGSM49AwEHoWQDWgAE")
os.environ.setdefault("VAPID_PUBLIC_KEY", "BDummyVapidPublicKeyForTestingOnlyDoNotUseInProduction123")
os.environ.setdefault("VAPID_CLAIMS_EMAIL", "test@test.com")

from config.settings import *  # noqa: E402

# Используем in-memory бэкенд для email — письма доступны через django.core.mail.outbox
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"  # type: ignore[assignment]

CELERY_TASK_ALWAYS_EAGER = True  # type: ignore[assignment]
CELERY_TASK_EAGER_PROPAGATES = True  # type: ignore[assignment]

# Заменяем Redis на in-memory кэш — устраняет зависимость от реального Redis в тестах
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}
