"""
Модуль для пользовательских исключений.

Этот модуль содержит определения пользовательских классов исключений,
которые используются для обработки различных ситуаций в коде.

Классы исключений:
- EmptyResponseError: Исключение для пустого ответа от API.
- TelegramMessageError: Исключение для ошибок при отправке
сообщений в Telegram.
"""


class EmptyResponseError(Exception):
    """
    Пустой ответ от API.

    Либо нет ключа homeworks, либо нет ключа current_date.
    Либо нет обоих ключей.
    """

    pass


class UnknownHomeworkStatusError(Exception):
    """Исключение для неизвестного статуса домашней работы."""

    pass


class MissingKeyError(Exception):
    """Ошибка при отсутствии ключа в ответе API."""

    pass


class EnvVarMissingError(Exception):
    """Ошибка отстутсвия переменных окружения."""

    pass


class APICallError(Exception):
    """Исключение для статуса отличного от 200."""

    pass
