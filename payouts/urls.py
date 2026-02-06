"""
Конфигурация URL-адресов API для приложения payouts.

Этот файл определяет маршруты (URL patterns) для API заявок на выплату.
Используется Django REST Framework Router для автоматической генерации
стандартных CRUD-эндпоинтов на основе ViewSet.

Основные маршруты:
    /api/payouts/          - Список заявок и создание новой (GET, POST)
    /api/payouts/{id}/     - Детали, обновление и удаление конкретной заявки (GET, PATCH, DELETE)

Особенности:
    - Используется DefaultRouter для автоматической генерации RESTful маршрутов
    - Все маршруты наследуют префикс из корневого urls.py проекта
    - Поддерживаются стандартные действия ViewSet: list, create, retrieve, update, partial_update, destroy

Альтернативный подход:
    При необходимости кастомной логики маршрутизации можно использовать явное определение
    маршрутов через as_view(), как показано в комментариях ниже.
"""

from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"payouts", views.PayoutViewSet)
urlpatterns = router.urls

"""
Альтернативный подход: явное определение маршрутов.

Используется в случаях, когда требуется:
- Кастомные URL-паттерны, не совпадающие со стандартными REST
- Подключение только части методов ViewSet
- Специфичные имена маршрутов (endpoint names)
- Кастомная логика в URL (например, разные префиксы)

Пример явного определения:

from django.urls import path
from .views import PayoutViewSet

# Создание отдельных представлений для разных методов
payout_list = PayoutViewSet.as_view({
    'get': 'list',
    'post': 'create'
})

payout_detail = PayoutViewSet.as_view({
    'get': 'func_in_class',
    'put': 'my_update',
    'patch': 'some_update',
    'delete': 'soft_delete'
})

# Кастомный endpoint для восстановления удаленных заявок
payout_restore = PayoutViewSet.as_view({
    'post': 'restore'
})

urlpatterns = [
    path('payouts/', payout_list, name='payout-list'),      # Логика GET и POST забирается из payout_list
    path('payouts/<int:pk>/', payout_detail, name='payout-detail'),
    path('payouts/<int:pk>/restore/', payout_restore, name='payout-restore'),
    # Или
    path('payouts/', PayoutViewSet.as_view({'get': 'list', 'post': 'create'}),  # и т.д.
]

Преимущества DefaultRouter:
1. Автоматическая генерация всех стандартных маршрутов
2. Поддержка вложенных роутеров (для связанных ресурсов)
3. Автоматическое определение имен маршрутов
4. Согласованность с RESTful принципами

Преимущества явного определения:
1. Полный контроль над URL-структурой
2. Возможность создания нестандартных endpoint'ов
3. Лучшая производительность при большом количестве маршрутов
4. Возможность использования разных ViewSet для разных операций

Рекомендации:
- Для стандартных CRUD операций используйте DefaultRouter
- Для сложных API с нестандартными endpoint'ами используйте явное определение
- Сочетайте оба подхода при необходимости
"""
