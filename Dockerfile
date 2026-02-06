FROM python:3.13-slim

# Убираем .pyc‑файлы, включаем «unbuffered» вывод
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Системные зависимости
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        libpq5 \
        build-essential \
        curl && \
    rm -rf /var/lib/apt/lists/*

# Рабочая директория внутри контейнера
WORKDIR /app

# Копируем файлы, необходимые для установки зависимостей.

COPY requirements.txt pyproject.toml poetry.lock* ./

# Обновляем pip и ставим зависимости из requirements.txt
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt && \
    rm -rf /root/.cache/pip

# Копируем остальной код проекта
COPY . .

# Создаём «незаширенного» пользователя
RUN adduser --disabled-password --gecos "" django_user
USER django_user

# Порт, на котором будет слушать Django/gunicorn
EXPOSE 8000

# Переменная‑переключатель.
#     Если DJANGO_RUNSERVER=1 – используем runserver (удобно в dev‑режиме);
#     иначе – production‑сервер gunicorn.
ENV DJANGO_RUNSERVER=1

# Команда запуска.
#     Сначала ждём готовности PostgreSQL, делаем миграцию,
#     а потом поднимаем приложение.
CMD if [ "$DJANGO_RUNSERVER" = "1" ]; then \
        python manage.py wait_for_db && \
        python manage.py migrate && \
        python manage.py runserver 0.0.0.0:8000; \
    else \
        python manage.py wait_for_db && \
        python manage.py migrate && \
        gunicorn SmartCollect_task.wsgi:application \
            --bind 0.0.0.0:8000 \
            --workers 3; \
    fi
