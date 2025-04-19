import logging
import os
import sys
import time

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
    """Отправляет сообщение в Telegram-чат."""
    try:
        if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            return True
        elif not PRACTICUM_TOKEN:
            logger.critical(
                'Отсутствует обязательная переменная окружения: '
                '"PRACTICUM_TOKEN" Программа принудительно остановлена.'
            )
            sys.exit(1)
        elif not TELEGRAM_TOKEN:
            logger.critical(
                'Отсутствует обязательная переменная окружения: '
                '"TELEGRAM_TOKEN" Программа принудительно остановлена.'
            )
            sys.exit(1)
        elif not TELEGRAM_CHAT_ID:
            logger.critical(
                'Отсутствует обязательная переменная окружения: '
                '"TELEGRAM_CHAT_ID" Программа принудительно остановлена.'
            )
            sys.exit(1)
    except Exception as error:
        logger.critical(f'Произошла ошибка {error}')
        sys.exit(1)


def send_message(bot, message):
    """Делает запрос к эндпоинту API-сервиса."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logger.debug('Сообщение успешно отправлено!')
    except Exception as error:
        logger.error(f'Ошибка {error}')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=timestamp
        )
        if homework_statuses.status_code == 200:
            homework_statuses = homework_statuses.json()
            return homework_statuses
        else:
            logger.error(
                f'Ошибка, Код ответа {homework_statuses.status_code}'
            )
            raise MissingValueException(
                f'Ошибка, Код ответа {homework_statuses.status_code}'
            )
    except requests.RequestException as error:
        logger.error(f'Ошибка при запросе {error}')
        raise ConnectionError(
            f'Произошла ошибка при запросе {error}'
        )


def check_response(response):
    """Проверяет на соответствие документации ответ API."""
    if 'homeworks' in response:
        response = response.get('homeworks')
        if not isinstance(response, list):
            logger.error(
                'Произошла ошибка тип данных не список в ответе работ API'
            )
            raise TypeError('Тип данных не список в ответе работ API')
        else:
            if not response:
                logger.debug('В списке нет новых статусов!')
                return False
            else:
                response = response[0]
                if not isinstance(response, dict):
                    text_error = (
                        'Произошла ошибка тип данных не '
                        'словарь в информации домашки'
                    )
                    logger.error(text_error)
                    raise TypeError(text_error)
                else:
                    if 'status' not in response:
                        logger.error('Ошибка, отстутствует ключ "status"')
                        raise MissingValueException(
                            'Не найден ключ "status"'
                        )
                    if 'homework_name' not in response:
                        logger.error(
                            'Ошибка, отстутствует ключ "homework_name"'
                        )
                        raise MissingValueException(
                            'Не найден ключ "homework_name"'
                        )
                    else:
                        response = response.get('status')
                        if response not in HOMEWORK_VERDICTS:
                            logger.error(
                                'Ошибка, неожиданный статус домашней работы!'
                            )
                            raise ValueError(
                                'Неожиданный статус домашней работы!'
                            )
                        else:
                            return True
    else:
        logger.error('Ошибка, нету ключа "homeworks"!')
        raise TypeError(
            'Произошла ошибка, не найден ключ "homeworks"'
        )


def parse_status(homework):
    """Извлекает из информации о
    конкретной домашней работе статус этой работы.
    """
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    if homework_name and homework_status and verdict:
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    elif not homework_name:
        logger.error('Произошла ошибка, нету ключа "homework_name"')
        raise MissingValueException('Ошибка, нету ключа "homework_name"')
    elif not homework_status:
        logger.error('Произошла ошибка, нету ключа "status"')
        raise MissingValueException('Ошибка, нету ключа "status"')
    elif not verdict:
        logger.error('Произошла ошибка с ключом "status"')
        raise MissingValueException('Ошибка с ключом "status"')


def main():
    """Основная логика работы бота."""
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    payload = {'from_date': timestamp}
    last_error = None
    status_hw_now = None
    status_hw_last = None

    while True:
        try:
            check_tokens()
            api_answer = get_api_answer(payload)
            check_api = check_response(api_answer)
            if not check_api:
                pass
            else:
                api_answer = api_answer.get('homeworks')[0]
                status_hw_now = parse_status(api_answer)
                if status_hw_now != status_hw_last:
                    send_message(bot, status_hw_now)
                status_hw_last = status_hw_now
            send_message(bot, 'f')
            bot.polling()
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message != last_error:
                send_message(bot, message)
            last_error = message
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
