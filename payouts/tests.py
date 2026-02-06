"""
Набор тестов для API заявок на выплату.

Этот модуль содержит интеграционные и юнит-тесты для проверки корректности работы
API выплат. Используется Django REST Framework APITestCase для тестирования
эндпоинтов с полным циклом HTTP запросов-ответов.

Структура тестов:
1. Создание заявок с проверкой запуска Celery-задач
2. Мягкое удаление и его последствия
3. Получение детальной информации
4. Валидация данных при создании
5. Ограничения на обновление полей
6. Проверка фильтрации списка

Особенности тестирования:
- Использование моков (mock) для изоляции Celery
- Проверка HTTP статус-кодов и структур ответов
- Тестирование бизнес-логики (мягкое удаление)
- Верификация работы кастомных менеджеров и фильтрации

Тестовые данные:
    valid_payload: Стандартные корректные данные для создания заявки
    invalid_payloads: Набор данных для проверки валидации

Запуск тестов:
    - Ысе тесты веб-приложения: python manage.py test
    - Все тесты приложения payouts: python manage.py test payouts
    - Конкретный тест: python manage.py test payouts.tests.PayoutAPITests.test_create_calls_celery_task
"""

from unittest.mock import patch
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from payouts.models import Payout


class PayoutAPITests(APITestCase):
    """
    Тестовый класс для API выплат.

    Наследуется от APITestCase Django REST Framework, что обеспечивает:
    - Автоматическое создание и откат транзакций для каждого теста
    - Доступ к клиенту API (self.client) для отправки HTTP-запросов
    - Вспомогательные методы для проверки ответов

    Фикстуры:
        setUp(): Выполняется перед каждым тестом, инициализирует общие данные

    Тестовые методы:
        Каждый метод начинается с test_ и тестирует отдельный сценарий работы API
    """

    def setUp(self):
        """
        Подготовка тестовых данных перед каждым тестом.

        Инициализирует:
            - URL-адреса API (используя reverse для динамического построения)
            - Корректные данные для создания заявки
            - Любые другие общие данные для тестов
        """

        # URL для списка заявок (генерируется роутером DefaultRouter)
        self.list_url = reverse("payout-list")  # /api/payouts
        self.valid_payload = {
            "amount": "2500.00",
            "currency": "RUB",
            "recipient_details": 'ООО "Ромашка", ИНН 7701234567',
            "comment": "Тестовая заявка",
        }

    @patch("payouts.views.process_payout_task")
    def test_create_calls_celery_task(self, mock_task):
        """
        Тест создания заявки с проверкой запуска Celery-задачи.

        Проверяет:
            1. Успешное создание заявки (статус 201)
            2. Корректный запуск задачи Celery
            3. Правильные параметры вызова задачи (ID заявки, задержка 5 сек)

        Использует mock для process_payout_task, чтобы:
            - Не зависеть от доступности Celery в тестовой среде
            - Проверить факт вызова задачи без реального выполнения
            - Измерить количество и параметры вызовов

        Аргументы:
            mock_task: Мок-объект для функции process_payout_task
        """

        # Отправка POST запроса для создания заявки
        response = self.client.post(
            self.list_url, data=self.valid_payload, format="json"
        )

        # Проверка успешного создания (201 Created)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Извлечение ID созданной заявки из ответа
        created_id = response.json()["id"]

        # Проверка, что Celery задача была вызвана один раз
        mock_task.apply_async.assert_called_once_with(args=[created_id], countdown=5)

    def test_soft_delete_hides_record(self):
        """
        Тест мягкого удаления заявки.

        Проверяет полный цикл мягкого удаления:
            1. Создание заявки
            2. Удаление через DELETE запрос
            3. Отсутствие заявки в API (список и детали)
            4. Сохранение записи в БД с флагом deleted=True

        Этот тест проверяет бизнес-логику мягкого удаления и работу
        кастомного менеджера PayoutManager, который фильтрует удаленные записи.
        """

        # Шаг 1: Создание заявки
        create_response = self.client.post(
            self.list_url, data=self.valid_payload, format="json"
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        payout_id = create_response.json()["id"]

        # Шаг 2: Мягкое удаление через DELETE
        delete_url = reverse("payout-detail", args=[payout_id])
        del_response = self.client.delete(delete_url)

        self.assertEqual(del_response.status_code, status.HTTP_204_NO_CONTENT)

        # Шаг 3: Проверка, что детали заявки больше недоступны
        detail_response = self.client.get(delete_url)
        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)

        # Шаг 4: Проверка, что заявка отсутствует в списке
        list_response = self.client.get(self.list_url)

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertNotIn(payout_id, [item["id"] for item in list_response.json()])

        # Шаг 5: Проверка, что запись осталась в БД с флагом deleted=True
        self.assertTrue(
            Payout.all_objects.filter(id=payout_id, deleted=True).exists(),
            msg="Запись должна быть помечена как deleted=True",
        )

    def test_retrieve_payout_detail(self):
        """
        Тест получения детальной информации о заявке.

        Проверяет:
            1. Успешное получение данных заявки (статус 200)
            2. Полноту возвращаемых полей
            3. Корректность значений полей
            4. Значение статуса по умолчанию (pending)

        Этот тест нужен для проверки сериализации и правильности
        отображения данных через API.
        """

        # Создание заявки
        create_response = self.client.post(
            self.list_url, data=self.valid_payload, format="json"
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        payout_id = create_response.json()["id"]
        detail_url = reverse("payout-detail", args=[payout_id])

        # Запрос детальной информации
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()

        # Проверка наличия всех ожидаемых полей
        expected_fields = {
            "id",
            "amount",
            "currency",
            "recipient_details",
            "status",
            "comment",
            "created_at",
            "updated_at",
        }

        self.assertEqual(set(data.keys()), expected_fields)

        # Проверка значений полей
        self.assertEqual(data["status"], "pending")

        for field in ("amount", "currency", "recipient_details", "comment"):
            self.assertEqual(data[field], self.valid_payload[field])

    def test_create_invalid_amount_returns_error(self):
        """
        Тест: валидация отрицательной суммы.

        Проверяет, что попытка создать заявку с отрицательной суммой:
        1. Возвращает статус 400 Bad Request
        2. Содержит ошибку для поля 'amount'
        3. Сообщение об ошибке указывает на необходимость положительного значения
        """

        invalid_payload = {
            "amount": "-10.00",
            "currency": "RUB",
            "recipient_details": 'ООО "Ромашка", ИНН 7701234567',
            "comment": "Неправильная сумма",
        }

        response = self.client.post(self.list_url, data=invalid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        data = response.json()

        # Поддержка обоих форматов ответа (с custom handler и без)
        errors = data.get("errors", data)

        # Поле amount должно присутствовать
        self.assertIn("amount", errors)

        amt_errors = errors["amount"]
        # Допускаем русский или английский вариант сообщения
        self.assertTrue(
            any(
                word in msg.lower()
                for msg in amt_errors
                for word in ("positive", "положительн", "больше", "0.01")
            ),
            msg=f"Ожидалась ошибка про положительность, получили: {amt_errors}",
        )

    def test_cannot_update_prohibited_fields(self):
        """
        Тест ограничений на обновление полей.

        Проверяет:
            1. Ошибку при попытке изменить запрещенные поля (amount, currency)
            2. Структуру сообщения об ошибке
            3. Содержание сообщения с указанием запрещенных полей

        Этот тест проверяет бизнес-логику, которая запрещает изменение
        суммы и валюты после создания заявки.
        """

        # Сначала создаём корректную запись
        create_response = self.client.post(
            self.list_url, data=self.valid_payload, format="json"
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        payout_id = create_response.json()["id"]
        patch_url = reverse("payout-detail", args=[payout_id])

        # Попытка изменения запрещенных полей
        bad_payload = {"amount": "9999.99", "currency": "USD"}

        response = self.client.patch(patch_url, data=bad_payload, format="json")

        # Проверка ошибки
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        data = response.json()

        # Проверка сообщения об ошибке на наличие ключевых слов
        self.assertIn("detail", data)
        self.assertIn("amount", data["detail"])
        self.assertIn("currency", data["detail"])

    def test_list_excludes_deleted_records(self):
        """
        Тест фильтрации удаленных записей в списке.

        Проверяет:
            1. Создание нескольких заявок
            2. Мягкое удаление одной из них
            3. Отсутствие удаленной заявки в списке
            4. Наличие активной заявки в списке

        Этот тест проверяет работу кастомного менеджера PayoutManager,
        который по умолчанию фильтрует записи с deleted=True.
        """

        # Создание первой заявки
        first = self.client.post(self.list_url, data=self.valid_payload, format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        # Создание второй заявки с измененным комментарием
        second_payload = self.valid_payload.copy()
        second_payload["comment"] = "Вторая заявка"
        second = self.client.post(self.list_url, data=second_payload, format="json")

        self.assertEqual(second.status_code, status.HTTP_201_CREATED)

        first_id = first.json()["id"]
        second_id = second.json()["id"]

        # Мягкое удаление первой заявки
        delete_url = reverse("payout-detail", args=[first_id])
        self.client.delete(delete_url)

        # Получение списка заявок
        list_response = self.client.get(self.list_url)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)

        ids_in_list = [item["id"] for item in list_response.json()]
        # Удаленная заявка не присутствует в списке
        self.assertNotIn(first_id, ids_in_list)
        # Активная заявка присутствует в списке
        self.assertIn(second_id, ids_in_list)
