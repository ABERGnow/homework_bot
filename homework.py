import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()

PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("PRACTICUM_TOKEN")

RETRY_PERIOD: int = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}

HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        logging.debug(f'Бот отправил сообщение: "{message}"')
        return bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.TelegramError as error:
        logging.error(f'Не удалось отправить сообщение: "{error}"')
        raise exceptions.SendMessageException(error)


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    params = {"from_date": timestamp}
    try:
        hw_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params,
        )
    except Exception as error:
        message = f"Ошибка {error} при запросе к {ENDPOINT}"
        raise exceptions.GetAPIAnswerException(message)
    status = hw_statuses.status_code
    if status != HTTPStatus.OK:
        message = f"Результа запроса к API: {status}"
        raise exceptions.GetAPIAnswerException(message)
    try:
        return hw_statuses.json()
    except Exception as error:
        message = f"Ошибка преобразования к типам данных Python {error}"
        raise exceptions.GetAPIAnswerException(message)


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if type(response) != dict:
        message = f"Не верный тип данных от сервера: {type(response)}"
        raise TypeError(message)
    if "homeworks" not in response:
        message = 'Отсутствует ключ "homeworks".'
        raise exceptions.CheckResponseException(message)
    hw_list = response["homeworks"]
    if type(hw_list) != list:
        message = f"Формат данных от API не в виде списка: {type(hw_list)}"
        raise TypeError(message)
    return hw_list


def parse_status(homework):
    """Извлекает статус о ДЗ."""
    if "homework_name" not in homework:
        message = 'Отсутствует ключ "homework_name".'
        raise KeyError(message)
    if "status" not in homework:
        message = 'Отсутствует ключ "status".'
        raise KeyError(message)
    homework_name = homework["homework_name"]
    homework_status = homework["status"]
    if homework_status in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[homework_status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    else:
        message = f'Неизвестный статус ДЗ "{homework_status}"'
        raise exceptions.ParseStatusException(message)


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        message = "Отсутствует обязательная переменная окружения."
        logger.critical(message)
        sys.exit("Работа бота завершена.")

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    current_status = ""
    current_error = ""

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if not len(homework):
                logger.info("Статус не обновлен")
            else:
                homework_status = parse_status(homework[0])
                if current_status == homework_status:
                    logger.info(homework_status)
                else:
                    current_status = homework_status
                    send_message(bot, homework_status)
        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            logger.error(message)
            if current_error != str(error):
                current_error = str(error)
                send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    main()
