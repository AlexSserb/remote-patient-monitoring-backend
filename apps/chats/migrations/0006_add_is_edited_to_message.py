"""Миграция: добавление поля is_edited в модель Message."""

from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Добавляет флаг редактирования сообщения."""

    dependencies = [
        ("chats", "0005_add_is_deleted_to_message"),
    ]

    operations = [
        migrations.AddField(
            model_name="message",
            name="is_edited",
            field=models.BooleanField(default=False, verbose_name="Отредактировано"),
        ),
    ]
