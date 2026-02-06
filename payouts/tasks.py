"""
Celery задачи для обработки выплат.

Этот модуль содержит задачи для фоновой обработки заявок на выплату.
Реализует асинхронную обработку с имитацией работы платежного шлюза,
автоматическими повторными попытками при ошибках.

Основные компоненты:
- BaseTaskWithRetry: Базовый класс с настройками повторных попыток
- process_payout_task: Основная задача обработки заявки

Особенности:
1. Автоматические повторные попытки при сбоях
2. Транзакционная безопасность с использованием select_for_update
3. Обработка мягкого удаления во время выполнения
4. Логирование всех этапов обработки
5. Имитация реального платежного шлюза с задержками и случайным результатом

Примечания:
- Celery настраивается в settings.py
- .env содержит изменяемые настраиваемые параметры CELERY_BROKER_URL и CELERY_RESULT_BACKEND
(можно расширить на все параметры)
"""

import time
import random
import logging
from celery import shared_task, Task
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from .models import Payout

logger = logging.getLogger(__name__)


class BaseTaskWithRetry(Task):
    """
    Базовый класс задачи Celery с автоматическими повторными попытками.

    Наследуется от celery.Task и добавляет настройки для автоматического
    повторного выполнения задачи при возникновении исключений.

    Параметры:
        autoretry_for (tuple): Типы исключений, при которых задача перезапускается
        retry_kwargs (dict): Параметры повторных попыток
        retry_backoff (bool): Увеличение интервала между попытками
        retry_jitter (bool): Случайное варьирование интервалов

    Примечание:
        Бэкдорф (backoff) и джиттер (jitter) помогают избежать "шторма"
        повторных попыток при массовых сбоях в распределенных системах.
    """

    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3, "countdown": 7}
    retry_backoff = True
    retry_jitter = True

    def run(self, *args, **kwargs):
        # Этот метод будет переопределен в дочерних задачах
        raise NotImplementedError("Подклассы должны реализовывать интерфейс 'run'.")


@shared_task(bind=True, base=BaseTaskWithRetry, name="process_payout_task")
def process_payout_task(self, payout_id):
    """
    Задача обработки заявки на выплату.

    Имитирует работу с платежным шлюзом:
    1. Получает заявку с блокировкой для предотвращения race condition
    2. Проверяет, что заявка активна и в статусе PENDING
    3. Обновляет статус на PROCESSING
    4. Имитирует задержку обработки (2-5 секунд)
    5. Случайно завершает как успешно или с ошибкой
    6. Обновляет финальный статус

    Args:
        payout_id (int): ID заявки на выплату для обработки

    Workflow:
        PENDING → PROCESSING → COMPLETED/FAILED

    Логика обработки:
        - 75% вероятность успеха, 25% вероятность ошибки
        - При удалении заявки во время обработки задача отменяется
        - При дублирующих вызовах игнорирует уже обрабатываемые заявки

    Примечания:
        - Использует select_for_update() для пессимистической блокировки
        - Включает проверку на мягкое удаление на всех этапах
        - Логирует все ключевые события для отладки
    """

    logger.info("Запуск обработки выплаты #%s", payout_id)

    try:
        with transaction.atomic():
            payout = Payout.objects.select_for_update().get(pk=payout_id)

            if payout.deleted:
                logger.info("Заявка #%s уже удалена – пропускаем", payout_id)
                return

            if payout.status != Payout.Status.PENDING:
                logger.warning("Выплата #%s уже обрабатывается/обработана.", payout_id)
                return

            payout.status = Payout.Status.PROCESSING
            payout.save(update_fields=["status"])

        # Имитация работы с платежным шлюзом
        delay = random.uniform(2, 5)
        time.sleep(delay)

        # Случайный результат (75% успех, 25% неудача)
        success = random.choice([True, True, True, False])

        # определяем статус результата заявки
        new_status = Payout.Status.COMPLETED if success else Payout.Status.FAILED

        # Фиксация результата с проверкой на удаление во время обработки
        with transaction.atomic():
            payout = Payout.objects.select_for_update().get(pk=payout_id)
            if payout.deleted:
                logger.info(
                    "Заявка #%s удалена после начала обработки – не меняем статус",
                    payout_id,
                )
                return

            # Установка финального статуса
            payout.status = new_status
            payout.save(update_fields=["status"])

        logger.info("Выплата #%s завершена: %s", payout_id, new_status)

    except ObjectDoesNotExist:
        logger.error("Выплата #%s не найдена", payout_id)
    except Exception as exc:
        logger.exception("Неожиданная ошибка при обработке выплаты #%s", payout_id)
        # Celery автоматически выполнит retry (в BaseTaskWithRetry)
        raise self.retry(exc=exc)
