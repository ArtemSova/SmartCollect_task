"""
Модели приложения payouts (заявки на выплаты).

Этот модуль определяет основные модели данных для системы выплат, включая:
- Модель Payout: основная модель заявок на выплату
- Кастомные менеджер для реализации soft-delete
- Перечисления для статусов и валют

Основные компоненты:
- PayoutManager: Кастомный менеджер для работы только с активными записями
- Payout: Основная модель с полями заявки на выплату
- Currency, Status: Перечисления для валют и статусов обработки

Основные концепции:
1. Soft-delete (мягкое удаление): записи помечаются как удаленные, но физически остаются в БД
2. Автоматическая фильтрация удаленных записей через кастомный менеджер
3. Валидация данных: как на уровне поля, так и на уровне модели
4. Автоматическое управление временными метками
"""

from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, RegexValidator


class PayoutManager(models.Manager):
    """
    Кастомный менеджер для модели Payout.

    Реализует логику мягкого удаления (soft-delete):
    - По умолчанию возвращает только активные записи (deleted=False)
    - Предоставляет явный метод для доступа ко всем записям
    """

    def get_queryset(self):
        """
        Возвращает QuerySet только с активными записями (deleted=False).

        Переопределяет стандартное поведение менеджера для автоматической
        фильтрации удаленных записей.
        """

        return super().get_queryset().filter(deleted=False)

    def all_with_deleted(self):
        """
        Возвращает все записи, включая удаленные.

        Используется для специальных случаев, когда нужен доступ
        к удаленным записям (для администратора, аналитики и т.п.).
        """

        return super().get_queryset()


class Payout(models.Model):
    """
    Модель заявки на выплату.

    Хранит информацию о запросе на денежный перевод, включая сумму,
    валюту, реквизиты получателя, статус обработки и комментарий.

    Особенности:
        - Мягкое удаление через флаг `deleted`
        - Автоматическая фильтрация удаленных записей через PayoutManager
        - Валидация данных на уровне поля и модели
        - Автоматическое управление временными метками
    """

    class Currency(models.TextChoices):
        """Доступные валюты для выплаты."""

        USD = "USD", "Доллар США"
        EUR = "EUR", "Евро"
        RUB = "RUB", "Рубль"

    class Status(models.TextChoices):
        """Статусы обработки заявки."""

        PENDING = "pending", "Ожидает обработки"
        PROCESSING = "processing", "В процессе обработки"
        COMPLETED = "completed", "Выполнена"
        FAILED = "failed", "Не удалось"

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Сумма выплаты (от 0.01)",
        verbose_name="Сумма",
    )

    currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        help_text="Трёхбуквенный код валюты ISO 4217",
        verbose_name="Валюта",
    )

    recipient_details = models.CharField(  #  Можно заменить на JSONField, если нужны сложные структурированные реквизиты.
        max_length=255,
        validators=[
            RegexValidator(
                regex=r"^[\w\s\-,.:;@]+$",
                message="Разрешены только буквы, цифры, пробел и знаки -_,.:;@",
            )
        ],
        help_text="Текстовое описание реквизитов получателя (max 255 символов)",
        verbose_name="Реквизиты",
    )

    deleted = models.BooleanField(
        default=False,
        help_text="Если true – запись считается удалённой",
        verbose_name="Удалено",
    )
    objects = PayoutManager()  # Только НЕ‑"удалённые" записи (по-умолчанию)
    all_objects = (
        models.Manager()
    )  # обычный manager без фильтра, для полного доступа (если понадобится)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text="Текущий статус заявки",
        verbose_name="Статус",
    )

    comment = models.TextField(
        blank=True,
        null=True,
        help_text="Необязательный комментарий",
        verbose_name="Комментарий",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Дата создания",
        verbose_name="Создано",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Дата последнего изменения",
        verbose_name="Изменено",
    )

    class Meta:
        """Метаданные модели."""

        verbose_name = "Заявка на выплату"
        verbose_name_plural = "Заявки на выплату"
        ordering = ["-created_at"]
        constraints = [
            # Ограничение на уровне БД: сумма должна быть положительной
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="amount_positive"
            )
        ]

    def __str__(self):
        """Строковое представление заявки."""
        return f"Заявка #{self.id} – {self.amount} {self.currency}"
