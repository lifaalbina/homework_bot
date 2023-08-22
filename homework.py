import logging
import os
import sys
import time
from contextlib import suppress
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import APICallError, APIConnectionError

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


def check_tokens() -> bool:
    """Проверка доступности переменных окружения."""
    checked_constants = (
        'PRACTICUM_TOKEN',
        'TELEGRAM_TOKEN',
        'TELEGRAM_CHAT_ID',
    )
    missing_tokens = [token for token in checked_constants
                      if not globals()[token]]
    if missing_tokens:
        missing_tokens_str = (', '.join(f'{token}'
                                        for token in missing_tokens))
        logging.critical(
            f'Отсутствует/ют переменные окружения: {missing_tokens_str}'
        )
        sys.exit('Некоторые переменные окружение недоступны. '
                 'Подробности в логах. Продолжение работы невозможно.')


def send_message(bot: telegram.Bot, message: str) -> None:
    """Отправка сообщения в Telegram чат."""
    logging.info('Начало отправки сообщения.')
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    logging.debug(f'Сообщение {message} отправлено.')


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
        logging.info('Начало отправки запроса.')
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)

    except requests.exceptions.RequestException as error:
        request_info = f'URL: {ENDPOINT}, Параметры: {payload}'
        raise APIConnectionError(
            f'При подключении к API возникла ошибка: {error}, {request_info}'
        ) from error

    if response.status_code != HTTPStatus.OK:
        raise APICallError(
            f'Статус-код ответа не 200 - {response.status_code}'
        )
    logging.info('Успешное получение ответа от API.')
    return response.json()


def check_response(response: dict) -> list:
    """
    Проверка ответа API на соответствие документации.

    В ответ должны вернуться два значения ключа:
    homeworks - значение этого ключа должен быть список.
    current_date - время отправки ответа.

    Сам ответ response - должен быть словарем.
    """
    if not isinstance(response, dict):
        raise TypeError(f'Ответ API не является словарем - {type(response)}')

    if 'homeworks' not in response:
        raise KeyError('Ожидаемый ключ отсутствует.')

    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError(f'Значение ключа "homeworks" не является списком - '
                        f'{type(homeworks)}')
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
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')

    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(
            f'Неизвестный статус работы- {homework_status}'
        )

    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    previous_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if not homeworks:
                logging.debug('В ответе отсутствуют новые статусы')
                continue
            message = parse_status(homeworks[0])
            if message != previous_message:
                send_message(bot, message)
                previous_message = message
            else:
                logging.info('Получено повторяющееся сообщение.')
            timestamp = response.get('current_date', timestamp)
        except telegram.error.TelegramError as error:
            logging.error(f'Ошибка отправки сообщения в Telegram: {error}')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(error, exc_info=True)
            if message != previous_message:
                with suppress(telegram.error.TelegramError):
                    send_message(bot, message)
                    previous_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s, '
               '%(name)s, %(funcName)s, %(lineno)d',
        stream=sys.stdout
    )
    main()
