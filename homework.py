import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot

from exceptions import MissingValueException

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s %(levelname)s %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)

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


def check_tokens():
    """Проверяет доступность переменных окружения."""
    env_dict = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    result = []
    for variable in env_dict:
        if env_dict[variable] is None or env_dict[variable] == '':
            result.append(variable)
    return result


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logger.debug('Сообщение успешно отправлено!')
    except Exception as error:
        logger.error('Ошибка %s', error)


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=timestamp
        )
        if homework_statuses.status_code != HTTPStatus.OK:
            raise MissingValueException(
                f'Ошибка, Код ответа {homework_statuses.status_code}, '
                f'URL {homework_statuses.url}, '
                f'headers {homework_statuses.headers}'
            )
        else:
            return homework_statuses.json()
    except requests.RequestException as error:
        raise ConnectionError(
            'Произошла ошибка при запросе %s', error
        )


def check_response(response):
    """Проверяет на соответствие документации ответ API."""
    if not isinstance(response, dict):
        raise TypeError('Тип данных не слоаврь в ответе API')
    if 'homeworks' not in response and 'current_date' not in response:
        raise TypeError(
            'Не найдены ключи "homeworks" или "current_date"'
        )
    response = response.get('homeworks')
    if not isinstance(response, list):
        raise TypeError('Тип данных не список в ответе работ API')
    return True


def parse_status(homework):
    """Извлекает статус домашней работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    if homework_name and homework_status and verdict:
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    elif not homework_name:
        raise MissingValueException('Ошибка, нету ключа "homework_name"')
    elif not homework_status:
        raise MissingValueException('Ошибка, нету ключа "status"')
    elif not verdict:
        raise MissingValueException('Ошибка с ключом "status"')


def main():
    """Основная логика работы бота."""
    if check_tokens():
        logger.critical(
            'Отсутствует обязательная переменная окружения'
        )
        raise MissingValueException(
            'Нет значения переменной'
        )
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    payload = {'from_date': timestamp}
    last_error = None
    status_hw_now = None
    status_hw_last = None

    while True:
        try:
            api_answer = get_api_answer(payload)
            check_api = check_response(api_answer)
            if check_api:
                api_answer = api_answer.get('homeworks')[0]
                status_hw_now = parse_status(api_answer)
                if status_hw_now != status_hw_last:
                    send_message(bot, status_hw_now)
                status_hw_last = status_hw_now
            bot.polling()
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message != last_error:
                send_message(bot, message)
            last_error = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
