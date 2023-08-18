import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (APICallError, EmptyResponseError, EnvVarMissingError,
                        MissingKeyError, UnknownHomeworkStatusError)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}
logger = logging.getLogger(__name__)


def check_tokens() -> bool:
    """Проверка доступности переменных окружения."""
    required_tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    for token in required_tokens:
        if not token:
            logging.critical(
                f"Отсутствует переменная окружения: {token}"
            )
            raise EnvVarMissingError('Отсутствует переменная окружения.')

    return True


def send_message(bot: telegram.Bot, message: str) -> None:
    """Отправка сообщения в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(f'Сообщение {message} отправлено.')
    except telegram.error.TelegramError as error:
        logger.error(f'Не удалось отправить сообщение {error}')


def get_api_answer(timestamp: int) -> dict:
    """
    Запрос к API Практикум.Домашка.

    Аргументы:
    timestamp - временная метка для фильтрации статусов домашних заданий.

    Возвращает:
    dict: ответ JSON, содержащий статусы домашних заданий.
    """
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != HTTPStatus.OK:
            raise APICallError('Пустой ответ от API.')
        return response.json()
    except requests.exceptions.RequestException as error:
        logger.error(f'При подключении к API возникла ошибка: {error}')
        return None


def check_response(response: dict) -> list:
    """
    Проверка ответа API на соответствие документации.

    В ответ должны вернуться два значения ключа:
    homeworks - значение этого ключа должен быть список.
    current_date - время отправки ответа.

    Сам ответ response - должен быть словарем.
    """
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем.')

    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Значение ключа "homeworks" не является списком.')

    if 'homeworks' not in response or 'current_date' not in response:
        logger.error('Пустой ответ от API.')
        raise EmptyResponseError('Пустой ответ от API.')
    return homeworks


def parse_status(homework: dict) -> str:
    """
    Извлекает из информации о конкретной домашней работе статус этой работы.

    В случае успеха, функция возвращает подготовленную
    для отправки в Telegram строку, содержащую один из
    вердиктов словаря HOMEWORK_VERDICTS.
    """
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_name is None:
        raise MissingKeyError('Отсутствует ключ "homework_name" в ответе API')

    if homework_status not in HOMEWORK_VERDICTS:
        error_message = f'Неизвестный статус работы - {homework_status}'
        logger.debug(error_message)
        raise UnknownHomeworkStatusError(f'Неизвестный статус работы'
                                         f'- {error_message}')

    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = 0

    if not check_tokens():
        logger.critical('Некоторые переменные окружение недоступны!!!')
        sys.exit('Некоторые переменные окружение недоступны. '
                 'Продолжение работы невозможно.')

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if not homework:
                message = 'Обновлений по статусам домашних работ нет.'
                logger.debug('В ответе отсутствуют новые статусы')
            else:
                message = parse_status(homework[0])
                timestamp = response['current_date']
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(error)
        finally:
            send_message(bot, message)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s, %(name)s',
        stream=sys.stdout
    )
    main()
