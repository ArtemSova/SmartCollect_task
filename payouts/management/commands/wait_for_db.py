"""
Модуль кастомной команды управления Django для ожидания доступности базы данных.

Этот модуль содержит команду `wait_for_db`, которая проверяет подключение к PostgreSQL
перед запуском приложения. Команда особенно полезна в контейнеризованных средах,
где база данных может запускаться дольше, чем основное приложение.

Основные функции:
- Проверка доступности базы данных с повторными попытками
- Информационное логирование процесса подключения
- Задержка между попытками для избежания нагрузки на СУБД
"""

import time
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    """
    Кастомная команда Django для ожидания доступности базы данных.

    Команда периодически проверяет подключение к базе данных (по умолчанию PostgreSQL)
    до тех пор, пока подключение не будет установлено или не будет достигнут
    максимальный лимит попыток (неявно, через бесконечный цикл с задержкой).

    Атрибуты:
        help (str): Краткое описание команды, отображаемое в справке.

    Методы:
        handle(*args, **options): Основной метод выполнения команды.

    Пример использования в Docker Compose:
        services:
          web:
            command: >
              sh -c "python manage.py wait_for_db &&
                     python manage.py migrate &&
                     python manage.py runserver 0.0.0.0:8000"
    """

    help = "Ждёт, пока база данных станет доступна. Используется при деплое (docker)"

    def handle(self, *args, **options):
        self.stdout.write("Проверка подключения к PostgreSQL...")
        db_conn = connections["default"]
        attempts = 0
        while True:
            try:
                c = db_conn.cursor()
                c.execute("SELECT 1;")
                self.stdout.write(self.style.SUCCESS("База готова!"))
                break
            except OperationalError:
                attempts += 1
                self.stdout.write(
                    f"Попытка {attempts}: БД еще не отвечает, ждём 2 сек..."
                )
                time.sleep(2)
