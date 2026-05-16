FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Копируем uv из официального образа
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Устанавливаем зависимости отдельным слоем — инвалидируется только при изменении lock-файла
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Копируем код приложения
COPY . .

# Создаём непривилегированного пользователя
RUN addgroup --system app \
    && adduser --system --ingroup app --no-create-home app \
    && mkdir -p /app/staticfiles \
    && chown -R app:app /app

USER app