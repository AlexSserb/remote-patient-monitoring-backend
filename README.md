# Remote Patient Monitoring — Backend

Серверная часть системы дистанционного мониторинга пациентов с эндокринными заболеваниями.

## О проекте

Система поддерживает три роли участников:

- **Доктор** — ведёт список прикреплённых пациентов и опекунов.
- **Пациент** — заполняет дневник здоровья, получает уведомления-напоминания.
- **Опекун** — может быть прикреплён к нескольким пациентам и вносить данные в их дневники; также получает уведомления о необходимости заполнения.

Аутентификация двухшаговая: email + пароль → OTP-код на почту → JWT-токены (access + refresh).

## Стек технологий

| Компонент | Технология |
|---|---|
| Фреймворк | Django 6, Django REST Framework |
| База данных | PostgreSQL |
| Кэш / брокер | Redis |
| Очередь задач | Celery |
| Менеджер пакетов | uv |
| Python | 3.14 |
| Линтер | Ruff |
| Проверка типов | ty |

## Запуск проекта

### 1. Установить зависимости

```bash
uv sync
```

### 2. Создать `.env` файл

Скопировать шаблон и заполнить переменные окружения:

```bash
cp .env.example .env
```

### 3. Применить миграции

```bash
uv run python manage.py migrate
```

### 4. Запустить сервер разработки

```bash
uv run python manage.py runserver
```

API-документация доступна по адресу `http://localhost:8000/api/docs/`.

## Запуск тестов

Тесты используют отдельные настройки (`monitoring/test_settings.py`), которые автоматически
применяются через `pytest.ini_options` в `pyproject.toml`. Реальный Redis не требуется —
кэш заменяется на in-memory backend, email — на локальный перехватчик.

### Запуск всех тестов

```bash
uv run pytest
```

### Запуск с подробным выводом

```bash
uv run pytest -v
```

### Запуск тестов конкретного модуля

```bash
uv run pytest tests/users/test_services.py -v
```

### Запуск тестов конкретного класса или метода

```bash
uv run pytest tests/users/test_views.py::TestLogin -v
uv run pytest tests/users/test_views.py::TestLogin::test_valid_credentials_return_200_and_pre_auth_token -v
```

### Структура тестов

```
tests/
├── conftest.py                  # общие фикстуры (пользователи, API-клиент, очистка кэша)
└── users/
    ├── test_models.py           # модель User и перечисление Role
    ├── test_managers.py         # менеджер UserManager (create_user, create_superuser)
    ├── test_services.py         # сервисный слой (OTP, JWT, email) — без обращения к БД
    ├── test_serializers.py      # валидация и side-эффекты сериализаторов
    └── test_views.py            # API-эндпоинты (интеграционные тесты)
```

## Проверка качества кода

```bash
# Линтинг и форматирование
uv run ruff check . && uv run ruff format .

# Проверка типов
uv run ty check
```
