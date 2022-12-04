import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

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


def check_tokens():
    """Проверка существования внешних переменных"""
    if PRACTICUM_TOKEN is None:
        message = 'Отсутствует токен практикума'
        logging.critical(message)
        return False
    if TELEGRAM_TOKEN is None:
        message = 'Отсутствует токен телеги'
        logging.critical(message)
        return False
    if TELEGRAM_CHAT_ID is None:
        message = 'Отсутствует id чата'
        logging.critical(message)
        return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в телеграм-чат"""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception:
        logging.error('Ошибка отправки сообщения в телеграм')
    logging.debug('Сообщение отправлено в телеграм')


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпойнту Практикум.Домашки"""
    try:
        homework = requests.get(ENDPOINT, headers=HEADERS, params=timestamp)
    except Exception as error:
        logging.error(f'Ошибка при запросе к основному API: {error}')
        return {}
    try:
        homework = requests.get(ENDPOINT, headers=HEADERS, params=timestamp)
    except ValueError:
        logging.exception(f'Возникла ошибка, текст ответа:{homework.text}')
        return {}
    if homework.status_code != HTTPStatus.OK:
        logging.error(f'Код ответа API: {homework.status_code}')
        homework.raise_for_status()
    try:
        return homework.json()
    except Exception as error:
        logging.error(f'Ошибка преобразования к формату json: {error}')
        return {}


def check_response(response):
    """Проверяет, что ответ от ПРАКТИКУМа соответствует ожидаемому"""
    if isinstance(response, dict) is False:
        message = f'responce вернул не словарь, а {type(response)}'
        logging.exception(message)
        raise TypeError(message)
    resp_list = response.get('homeworks')
    if isinstance(resp_list, list) is False:
        message = f'responce вернул не список, а {type(resp_list)}'
        logging.exception(message)
        raise TypeError(message)
    if 'homeworks' not in response.keys():
        message = 'нет ключа homeworks'
        logging.error(message)
        raise TypeError(message)
    return resp_list


def parse_status(homework):
    """Создает сообщение о статусе домашнего задания"""
    try:
        homework_name = homework['homework_name']
    except KeyError as exc:
        message = 'В ответе отсутствует ключ homework_name'
        logging.error(message)
        raise KeyError(message) from exc
    try:
        homework_status = homework['status']
    except KeyError as exc:
        message = 'В ответе сервера отсутствует ключ status'
        logging.error(message)
        raise KeyError(message) from exc
    if homework_status in HOMEWORK_VERDICTS.keys():
        verdict = HOMEWORK_VERDICTS[homework_status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    else:
        logging.error(
            f'Ошибка статуса: {homework_status}\
            не входит в {HOMEWORK_VERDICTS.keys()}'
        )
        raise TypeError('Нет такого статуса')


def main():
    """Основная логика работы бота."""
    logging.basicConfig(
        level=logging.INFO,
        filename='main.log',
        filemode='w',
        format='%(asctime)s, %(levelname)s, %(name)s, %(message)s'
    )
    last_message = 'none'
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - 86400
    if check_tokens() is True:
        while True:
            try:
                response_result = get_api_answer(timestamp)
                homeworks = check_response(response_result)
                logging.info("Список домашних работ получен")
                if len(homeworks) > 0:
                    status = parse_status(homeworks[0])
                    if status != last_message:
                        send_message(bot, status)
                        last_message = status
                else:
                    logging.info("Новые задания не обнаружены")
            except Exception as error:
                send_message(bot, f'Сбой в работе программы: {error}')
            finally:
                time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
