"""
Кастомный обработчик исключений для Django REST Framework.

Модуль предоставляет функцию custom_exception_handler, которая заменяет
стандартный обработчик исключений DRF для унификации формата ответов при ошибках.
Все исключения преобразуются в единый JSON-формат с предсказуемой структурой,
что упрощает обработку ошибок на клиентской стороне.

Формат ответа при ошибке:
{
    "code": 400,                      # HTTP-статус код
    "detail": "Описание ошибки",      # Общее описание ошибки
    "errors": {                       # Детальные ошибки по полям (опционально)
        "field_name": ["Сообщение об ошибке", "Другое сообщение"],
        "another_field": ["Ошибка валидации"]
    }
}

Использование:
    В settings.py DRF нужно указать:
    REST_FRAMEWORK = {
        'EXCEPTION_HANDLER': 'payouts.exceptions.custom_exception_handler',
    }

Особенности:
    - Обрабатывает как исключения DRF, так и необработанные исключения
    - Преобразует стандартный формат DRF в единый кастомный формат
    - Обеспечивает обратную совместимость со стандартным обработчиком
    - Поддерживает детализацию ошибок валидации по полям
"""

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    """
    Кастомный обработчик исключений для DRF.

    Преобразует любой ответ с ошибкой в стандартизированный JSON-формат.
    Обрабатывает как стандартные исключения DRF, так и необработанные
    исключения сервера (500 ошибки).

    Args:
        exc (Exception): Исключение, которое было вызвано.
        context (dict): Словарь с контекстом запроса, содержит:
            - 'view': текущий View
            - 'args': позиционные аргументы
            - 'kwargs': именованные аргументы
            - 'request': объект запроса

    Returns:
        Response: Ответ с ошибкой в стандартизированном формате.

    Формат ответа:
        Стандартные ошибки (400-499):
        {
            "code": 400,
            "detail": "Описание основной ошибки",
            "errors": {
                "field_name": ["Сообщение об ошибке"],
                "nested_field": {
                    "sub_field": ["Ошибка вложенного поля"]
                }
            }
        }

        Серверные ошибки (500):
        {
            "code": 500,
            "detail": "Внутренняя ошибка сервера",
            "errors": {}
        }

    Примечание:
    - Можно добавить логирование
    - Можно расписать ответы на каждый статус-код
    """

    # Получаем стандартный ответ от DRF обработчика
    response = exception_handler(exc, context)

    if response is None:  # Необработанные исключения – например, 500
        return Response(  # Возвращаем стандартизированный формат для любых непредвиденных ошибок
            {
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "detail": "Внутренняя ошибка сервера",
                "errors": {},
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    custom_response = {  # Кастомная структура ответа на основе стандартного ответа DRF
        "code": response.status_code,
        "detail": response.data.get("detail") or "Ошибка запроса",
        "errors": {},
    }

    for (
        key,
        value,
    ) in (
        response.data.items()
    ):  # Если в ответе есть поле-по-полям ошибки – переносим их в структурированный вид
        if key == "detail":  # Пропускаем поле 'detail', так как оно уже обработано выше
            continue
        custom_response["errors"][key] = value if isinstance(value, list) else [value]

    return Response(custom_response, status=response.status_code)
