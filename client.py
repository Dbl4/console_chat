"""Программа-клиент"""

import sys
import json
import socket
import time
import argparse
import logging
import threading
import logs.config.config_client_log
from errors import ReqFieldMissingError, ServerError, IncorrectDataRecivedError
from common.variables import DEFAULT_PORT, DEFAULT_IP_ADDRESS, \
    ACTION, TIME, USER, ACCOUNT_NAME, SENDER, PRESENCE, RESPONSE, ERROR, MESSAGE, MESSAGE_TEXT, DESTINATION, EXIT
from common.utils import get_message, send_message
from decos import Log

# Инициализация клиентского логера
LOGGER = logging.getLogger('client')


def print_help():
    """Функция выводящяя справку по использованию"""
    print('Поддерживаемые команды:')
    print('message - отправить сообщение. Кому и текст будет запрошены отдельно.')
    print('help - вывести подсказки по командам')
    print('exit - выход из программы')


class Client:

    @Log()
    def create_exit_message(self, account_name):
        self.account_name = account_name
        """Функция создаёт словарь с сообщением о выходе"""
        return {
            ACTION: EXIT,
            TIME: time.time(),
            ACCOUNT_NAME: account_name
        }

    @Log()
    def message_from_server(self, sock, my_username):
        self.sock = sock
        self.my_usename = my_username
        """Функция - обработчик сообщений других пользователей, поступающих с сервера"""
        while True:
            try:
                message = get_message(sock)
                if ACTION in message and message[ACTION] == MESSAGE and \
                        SENDER in message and DESTINATION in message \
                        and MESSAGE_TEXT in message and message[DESTINATION] == my_username:
                    print(f'\nПолучено сообщение от пользователя {message[SENDER]}:'
                          f'\n{message[MESSAGE_TEXT]}')
                    LOGGER.info(f'Получено сообщение от пользователя {message[SENDER]}:'
                                f'\n{message[MESSAGE_TEXT]}')
                else:
                    LOGGER.error(f'Получено некорректное сообщение с сервера: {message}')
            except IncorrectDataRecivedError:
                LOGGER.error(f'Не удалось декодировать полученное сообщение.')
            except (OSError, ConnectionError, ConnectionAbortedError,
                    ConnectionResetError, json.JSONDecodeError):
                LOGGER.critical(f'Потеряно соединение с сервером.')
                break

    @Log()
    def create_message(self, sock, account_name='Guest'):
        """
        Функция запрашивает кому отправить сообщение и само сообщение,
        и отправляет полученные данные на сервер
        :param sock:
        :param account_name:
        :return:
        """
        self.sock = sock
        self.account_name = account_name
        to_user = input('Введите получателя сообщения: ')
        message = input('Введите сообщение для отправки: ')
        message_dict = {
            ACTION: MESSAGE,
            SENDER: account_name,
            DESTINATION: to_user,
            TIME: time.time(),
            MESSAGE_TEXT: message
        }
        LOGGER.debug(f'Сформирован словарь сообщения: {message_dict}')
        try:
            send_message(sock, message_dict)
            LOGGER.info(f'Отправлено сообщение для пользователя {to_user}')
        except:
            LOGGER.critical('Потеряно соединение с сервером.')
            sys.exit(1)

    @Log()
    def user_interactive(self, sock, username):
        self.sock = sock
        self.username = username
        """Функция взаимодействия с пользователем, запрашивает команды, отправляет сообщения"""
        print_help()
        print(f"Добро пожаловать, {username}!")
        while True:
            command = input('Введите команду: ')
            if command == 'message':
                self.create_message(sock, username)
            elif command == 'help':
                print_help()
            elif command == 'exit':
                send_message(sock, self.create_exit_message(username))
                print('Завершение соединения.')
                LOGGER.info('Завершение работы по команде пользователя.')
                # Задержка неоходима, чтобы успело уйти сообщение о выходе
                time.sleep(0.5)
                break
            else:
                print('Команда не распознана, попробойте снова. help - вывести поддерживаемые команды.')

    @Log()
    def create_presence(self, account_name='Guest'):
        self.account_name = account_name
        """Функция генерирует запрос о присутствии клиента"""
        out = {
            ACTION: PRESENCE,
            TIME: time.time(),
            USER: {
                ACCOUNT_NAME: account_name
            }
        }
        LOGGER.debug(f'Сформировано {PRESENCE} сообщение для пользователя {account_name}')
        return out

    @Log()
    def process_response_ans(self, message):
        """
        Функция разбирает ответ сервера на сообщение о присутствии,
        возращает 200 если все ОК или генерирует исключение при ошибке
        """
        self.message = message
        LOGGER.debug(f'Разбор приветственного сообщения от сервера: {message}')
        if RESPONSE in message:
            if message[RESPONSE] == 200:
                return '200 : OK'
            elif message[RESPONSE] == 400:
                raise ServerError(f'400 : {message[ERROR]}')
        raise ReqFieldMissingError(RESPONSE)

    @Log()
    def arg_parser(self):
        """Создаём парсер аргументов коммандной строки
        и читаем параметры, возвращаем 3 параметра
        """
        parser = argparse.ArgumentParser()
        parser.add_argument('addr', default=DEFAULT_IP_ADDRESS, nargs='?')
        parser.add_argument('port', default=DEFAULT_PORT, type=int, nargs='?')
        parser.add_argument('-n', '--name', default='None', nargs='?')
        namespace = parser.parse_args(sys.argv[1:])
        server_address = namespace.addr
        server_port = namespace.port
        client_name = namespace.name

        # проверим подходящий номер порта
        if not 1023 < server_port < 65536:
            LOGGER.critical(
                f'Попытка запуска клиента с неподходящим номером порта: {server_port}. '
                f'Допустимы адреса с 1024 до 65535. Клиент завершается.')
            sys.exit(1)

        return server_address, server_port, client_name

    # версия без логгирования в комментариях
    """
    def main(self):
        '''Загружаем параметы коммандной строки'''
        # client.py 192.168.1.2 8079
        try:
            server_address = sys.argv[1]
            server_port = int(sys.argv[2])
            if server_port < 1024 or server_port > 65535:
                raise ValueError
        except IndexError:
            server_address = DEFAULT_IP_ADDRESS
            server_port = DEFAULT_PORT
        except ValueError:
            print('В качестве порта может быть указано только число в диапазоне от 1024 до 65535.')
            sys.exit(1)

        # Инициализация сокета и обмен

        transport = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        transport.connect((server_address, server_port))
        message_to_server = self.create_presence()
        send_message(transport, message_to_server)
        try:
            answer = self.process_ans(get_message(transport))
            print(answer)
        except (ValueError, json.JSONDecodeError):
            print('Не удалось декодировать сообщение сервера.')
    """

    def main(self):
        """Сообщаем о запуске"""
        print('Консольный месседжер. Клиентский модуль.')

        # Загружаем параметы коммандной строки
        server_address, server_port, client_name = self.arg_parser()

        # Если имя пользователя не было задано, необходимо запросить пользователя.
        if not client_name:
            client_name = input('Введите имя пользователя: ')

        LOGGER.info(
            f'Запущен клиент с парамертами: адрес сервера: {server_address}, '
            f'порт: {server_port}, имя пользователя: {client_name}')

        # Инициализация сокета и сообщение серверу о нашем появлении
        try:
            transport = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            transport.connect((server_address, server_port))
            send_message(transport, self.create_presence(client_name))
            answer = self.process_response_ans(get_message(transport))
            LOGGER.info(f'Установлено соединение с сервером. Ответ сервера: {answer}')
            print(f'Установлено соединение с сервером.')
        except json.JSONDecodeError:
            LOGGER.error('Не удалось декодировать полученную Json строку.')
            sys.exit(1)
        except ServerError as error:
            LOGGER.error(f'При установке соединения сервер вернул ошибку: {error.text}')
            sys.exit(1)
        except ReqFieldMissingError as missing_error:
            LOGGER.error(f'В ответе сервера отсутствует необходимое поле {missing_error.missing_field}')
            sys.exit(1)
        except (ConnectionRefusedError, ConnectionError):
            LOGGER.critical(
                f'Не удалось подключиться к серверу {server_address}:{server_port}, '
                f'конечный компьютер отверг запрос на подключение.')
            sys.exit(1)
        else:
            # Если соединение с сервером установлено корректно,
            # запускаем клиенский процесс приёма сообщний
            receiver = threading.Thread(target=self.message_from_server, args=(transport, client_name))
            receiver.daemon = True
            receiver.start()

            # затем запускаем отправку сообщений и взаимодействие с пользователем.
            user_interface = threading.Thread(target=self.user_interactive, args=(transport, client_name))
            user_interface.daemon = True
            user_interface.start()
            LOGGER.debug('Запущены процессы')

            # Watchdog основной цикл, если один из потоков завершён,
            # то значит или потеряно соединение или пользователь
            # ввёл exit. Поскольку все события обработываются в потоках,
            # достаточно просто завершить цикл.
            while True:
                time.sleep(1)
                if receiver.is_alive() and user_interface.is_alive():
                    continue
                break


if __name__ == '__main__':
    Client().main()
