"""
ViewSet для API заявок на выплату.

Этот модуль реализует CRUD-эндпоинты для работы с заявками на выплату через Django REST Framework.
Предоставляет стандартные операции с дополнительной бизнес-логикой: мягкое удаление,
ограниченное обновление полей и асинхронную обработку через Celery.

Основные функции:
- Создание заявки с автоматической постановкой в очередь на обработку
- Просмотр списка и деталей только активных (не удаленных) заявок
- Ограниченное обновление (только статус и комментарий)
- Мягкое удаление с пометкой флага deleted=True
- Интеграция с Celery для фоновой обработки

HTTP методы:
    GET    /api/payouts/         - список активных заявок
    GET    /api/payouts/{id}/    - детали конкретной заявки (если не удалена)
    POST   /api/payouts/         - создание новой заявки
    PATCH  /api/payouts/{id}/    - частичное обновление (только статус и комментарий)
    DELETE /api/payouts/{id}/    - мягкое удаление (deleted=True)
"""

import logging
from rest_framework import viewsets, status, serializers
from rest_framework.response import Response
from .models import Payout
from .serializers import PayoutSerializer
from .tasks import process_payout_task

logger = logging.getLogger(__name__)


# pylint: disable=too-many-ancestors
class PayoutViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления заявками на выплату.

    Обеспечивает полный цикл CRUD операций с дополнительной бизнес-логикой:
    - Автоматический запуск обработки при создании
    - Защита от изменения неизменяемых полей
    - Soft-delete (мягкое удаление) вместо физического
    """

    # QuerySet автоматически фильтрует удаленные записи через кастомный менеджер в serializers.py
    queryset = Payout.objects.all()
    serializer_class = PayoutSerializer

    # Ограничиваем доступные HTTP-методы (исключаем PUT, можно расширить)
    http_method_names = ["get", "post", "patch", "delete"]

    def perform_create(self, serializer):
        """
        Создание заявки с запуском асинхронной обработки.

        После успешного сохранения заявки отправляет задачу в очередь Celery
        для фоновой обработки. Если постановка задачи не удалась, меняет статус
        заявки на FAILED и возвращает ошибку клиенту.

        Args:
            serializer: Валидированный сериализатор с данными заявки

        Raises:
            serializers.ValidationError: Если не удалось поставить задачу в очередь
        """

        payout = serializer.save()

        try:
            # Отправляем задачу в очередь Celery с задержкой 5 секунд (изменить на проде)
            process_payout_task.apply_async(args=[payout.id], countdown=5)
        except Exception as exc:
            logger.exception("Не удалось поставить задачу в очередь")

            # Меняем статус на FAILED в случае ошибки постановки задачи
            payout.status = Payout.Status.FAILED
            payout.save(update_fields=["status"])

            raise serializers.ValidationError(
                {"detail": "Сервис фоновых задач недоступен. Попробуйте позже."}
            ) from exc

    def partial_update(self, request, *args, **kwargs):
        """
        Частичное обновление заявки.

        Разрешает изменение только полей:
        - status: Статус заявки
        - comment: Комментарий

        Args:
            request: Объект HTTP-запроса
            *args: Дополнительные позиционные аргументы
            **kwargs: Дополнительные именованные аргументы

        Returns:
            Response: Обновленный объект или ошибка валидации
        """

        self.get_object()

        # Определяем разрешенные для изменения поля
        allowed_fields = {"status", "comment"}
        incoming = set(request.data.keys())
        illegal = incoming - allowed_fields

        # Проверяем, что запрос не содержит запрещенных полей
        if illegal:
            return Response(
                {"detail": f'Нельзя менять поля: {", ".join(illegal)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """
        Мягкое удаление заявки.

        Вместо физического удаления из базы данных помечает запись
        как deleted=True. Если запись уже удалена, возвращает 204 без изменений.

        Args:
            request: Объект HTTP-запроса
            *args: Дополнительные позиционные аргументы
            **kwargs: Дополнительные именованные аргументы

        Returns:
            Response: 204 No Content при успешном удалении
        """

        instance = self.get_object()

        # Если запись уже удалена - возвращаем 204 без изменений
        if instance.deleted:
            return Response(status=status.HTTP_204_NO_CONTENT)

        # Помечаем запись как удаленную
        instance.deleted = True
        instance.save(update_fields=["deleted"])

        return Response(status=status.HTTP_204_NO_CONTENT)
