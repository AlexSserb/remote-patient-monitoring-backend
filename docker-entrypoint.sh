#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Загружаем фикстуры только при первом запуске (пустая таблица пользователей)
if python manage.py shell -c \
    "from django.contrib.auth import get_user_model; \
     import sys; sys.exit(0 if get_user_model().objects.exists() else 1)" 2>/dev/null; then
    echo "Database already populated, skipping fixtures."
else
    echo "Loading fixtures..."
    python manage.py loaddata \
        fixtures/users/users.json \
        fixtures/users/caregiver_patients.json \
        fixtures/users/doctor_patients.json \
        fixtures/diagnoses/diagnoses.json \
        fixtures/diagnoses/metrics.json \
        fixtures/diagnoses/diagnosis_metrics.json \
        fixtures/diagnoses/patient_diagnoses.json
fi