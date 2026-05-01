.PHONY: load-fixtures reset-db

# Загрузить тестовые данные в существующую базу (перезапишет записи с совпадающими PK)
load-fixtures:
	uv run python manage.py loaddata users diagnoses metrics diagnosis_metrics patient_diagnoses doctor_patients caregiver_patients

# Сбросить базу, применить миграции заново и загрузить тестовые данные
reset-db:
	uv run python manage.py flush --no-input
	uv run python manage.py migrate
	uv run python manage.py loaddata users diagnoses metrics diagnosis_metrics patient_diagnoses doctor_patients caregiver_patients
