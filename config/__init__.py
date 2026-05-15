"""Конфигурация Django-проекта remote-patient-monitoring."""

from .celery import app as celery_app

__all__ = ["celery_app"]
