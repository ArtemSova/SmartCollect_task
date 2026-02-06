"""
Сериализаторы для модели Payout.

Этот модуль содержит сериализаторы Django REST Framework для преобразования
данных модели Payout в JSON и обратно. Обеспечивает валидацию входящих данных
и контроль доступных полей для API.

Основные компоненты:
- PayoutSerializer: Основной сериализатор для полного цикла работы с заявками
- RECIPIENT_VALIDATOR: Глобальный валидатор для реквизитов получателя

Особенности:
1. Кастомная валидация полей amount, currency, status
2. Расширенный валидатор для recipient_details
3. Автоматическая обработка временных меток и ID
"""

from django.core.validators import RegexValidator
from rest_framework import serializers
from .models import Payout

# Глобальный валидатор для реквизитов получателя
RECIPIENT_VALIDATOR = RegexValidator(
    regex=r"^[\w\s\-\.,:;@\"\'\(\)\[\]\#%&*+=]+$",
    message="Разрешены буквы, цифры, пробел и обычные знаки пунктуации.",
)


class PayoutSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели Payout.

    Обеспечивает сериализацию/десериализацию заявок на выплату
    с валидацией данных и контролем доступа к полям.

    Поля:
        id (read-only): Уникальный идентификатор заявки
        amount: Сумма выплаты (положительное число)
        currency: Валюта (USD, EUR, RUB)
        recipient_details: Реквизиты получателя (до 255 символов)
        status: Статус заявки (pending, processing, completed, failed)
        comment: Комментарий (опционально)
        created_at (read-only): Дата создания
        updated_at (read-only): Дата последнего обновления
    """

    # Явное объявление read-only полей для ясности
    id = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    # Переопределение поля с использованием глобального валидатора
    recipient_details = serializers.CharField(
        max_length=255,
        validators=[RECIPIENT_VALIDATOR],
        help_text="Реквизиты получателя (до 255 символов)",
    )

    class Meta:
        """
        Настройки сериализатора:
        - model: Модель Payout
        - fields: Все поля модели для сериализации
        - read_only_fields: Системные поля (id, даты создания и обновления)
        """

        model = Payout
        fields = [
            "id",
            "amount",
            "currency",
            "recipient_details",
            "status",
            "comment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_amount(self, value):
        """
        Проверка, что сумма положительная.

        Args:
            value: Проверяемое значение суммы

        Returns:
            Decimal: Валидное значение суммы

        Raises:
            serializers.ValidationError: Если сумма <= 0
        """
        if value <= 0:
            raise serializers.ValidationError("Сумма должна быть положительной.")
        return value

    def validate_currency(self, value):
        """
        Проверка, что валюта находится в списке допустимых.

        Args:
            value: Проверяемое значение валюты

        Returns:
            str: Валидный код валюты

        Raises:
            serializers.ValidationError: Если валюта недопустима
        """

        if value not in dict(Payout.Currency.choices):
            raise serializers.ValidationError("Недопустимая валюта.")
        return value

    def validate_status(self, value):
        """
        Проверка, что статус находится в списке допустимых.

        Args:
            value: Проверяемое значение статуса

        Returns:
            str: Валидный статус

        Raises:
            serializers.ValidationError: Если статус недопустим
        """

        allowed = dict(Payout.Status.choices).keys()
        if value not in allowed:
            raise serializers.ValidationError("Недопустимый статус.")
        return value
