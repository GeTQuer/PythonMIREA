import tempfile
import threading
import time
import unittest
from http import HTTPStatus
from pathlib import Path
from urllib.error import HTTPError

from hypothesis import settings, strategies as st
from hypothesis.stateful import Bundle, RuleBasedStateMachine
from hypothesis.stateful import initialize, invariant, rule

from src.http_api import create_server
from src.http_client import ApiClient
from src.storage import FileStore


TEXT = st.text(alphabet="abcXYZ012 <>&", max_size=8)


class HttpMachine(RuleBasedStateMachine):
    """Проверять HTTP API с помощью независимой модели состояния."""

    entity_ids = Bundle("entities")
    command_ids = Bundle("commands")
    store_class = FileStore
    suffix = ".json"

    def __init__(self):
        """Создать временное хранилище, сервер, клиент и модель."""
        super().__init__()
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / ("database" + self.suffix)
        self.store = self.store_class(self.path)
        options = {"host": "127.0.0.1", "port": "0",
                   "username": "student", "password": "student",
                   "test_mode": "true"}
        self.server = create_server(options, self.store)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.url = "http://127.0.0.1:" + str(self.server.server_port)
        self.client = ApiClient(self.url)
        self.entities = []
        self.commands = []
        self.results = []
        self.now = int(time.time())

    def teardown(self):
        """Остановить сервер и освободить временные ресурсы."""
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()
        self.server.jobs.close()
        self.store.close()
        self.directory.cleanup()

    def check_record(self, actual, expected):
        """Сравнить фактические данные с независимым ожиданием."""
        assert actual == expected, f"Получено {actual}, ожидалось {expected}"

    @initialize(locale=TEXT, argument=TEXT)
    def cover_routes(self, locale, argument):
        """В начале сценария проверить все маршруты и типовые ошибки."""
        entity = self.submit_entity(locale, "browser")
        self.update_entity(entity, locale + "x")
        command = self.submit_command(entity, argument)
        self.update_command(command, argument + "x")
        self.fetch_command(entity)
        self.fetch_result(command)
        self.fetch_entity()
        self.fetch_report()
        self.reject_credentials()
        self.reject_invalid_data()
        self.check_time_boundary()

    @rule(target=entity_ids, locale=TEXT, user_agent=TEXT)
    def submit_entity(self, locale, user_agent):
        """Создать сущность и сравнить ответ с ожидаемой записью."""
        expected = {"identifier": str(len(self.entities)),
                    "created": str(self.now), "locale": locale,
                    "user_agent": user_agent}
        actual = self.client.api_submit_entity(
            locale=locale, user_agent=user_agent, created=self.now,
        )
        self.check_record(actual, expected)
        self.entities.append(expected)
        return expected["identifier"]

    @rule(entity=entity_ids, locale=TEXT)
    def update_entity(self, entity, locale):
        """Изменить локаль сущности и проверить ответ."""
        expected = {**self.entities[int(entity)], "locale": locale}
        actual = self.client.api_update_entity(entity, locale=locale)
        self.check_record(actual, expected)
        self.entities[int(entity)] = expected

    @rule(target=command_ids, entity=entity_ids, argument=TEXT)
    def submit_command(self, entity, argument):
        """Создать команду и добавить ожидаемый тестовый результат."""
        expected = {"identifier": str(len(self.commands)),
                    "created": str(self.now), "entity": entity,
                    "argument": argument, "tags": "", "status": "queued",
                    "started": "0"}
        actual = self.client.api_submit_command(
            entity, argument=argument, created=self.now,
        )
        self.check_record(actual, expected)
        self.commands.append(expected)
        self.results.append({"command": expected["identifier"],
                             "status": "test", "response": "test mode"})
        return expected["identifier"]

    @rule(command=command_ids, argument=TEXT)
    def update_command(self, command, argument):
        """Изменить аргумент команды и проверить ответ."""
        expected = {**self.commands[int(command)], "argument": argument}
        actual = self.client.api_update_command(command, argument=argument)
        self.check_record(actual, expected)
        self.commands[int(command)] = expected

    @rule()
    def fetch_entity(self):
        """Сравнить список сущностей сервера с моделью."""
        self.check_record(self.client.api_fetch_entity(), self.entities)

    @rule(entity=entity_ids)
    def fetch_command(self, entity):
        """Проверить список команд выбранной сущности."""
        expected = [row for row in self.commands if row["entity"] == entity]
        self.check_record(self.client.api_fetch_command(entity), expected)

    @rule(command=command_ids)
    def fetch_result(self, command):
        """Проверить ожидаемые результаты выбранной команды."""
        actual = self.client.api_fetch_result(command)
        expected = [row for row in self.results if row["command"] == command]
        assert len(actual) == len(expected)
        for row, wanted in zip(actual, expected):
            self.check_record({key: row[key] for key in wanted}, wanted)

    def expected_report(self):
        """Построить ожидаемый отчёт по данным тестовой модели."""
        rows = []
        for entity in self.entities:
            if int(entity["created"]) < int(time.time()) - 360:
                continue
            arguments = [row["argument"] for row in self.commands
                         if row["entity"] == entity["identifier"]] or [None]
            for argument in arguments:
                row = {"argument": argument, "locale": entity["locale"],
                       "user_agent": entity["user_agent"]}
                if row not in rows:
                    rows.append(row)
        return rows

    @rule()
    def fetch_report(self):
        """Сравнить отчёт сервера с ожидаемым."""
        self.check_record(self.client.api_fetch_report(),
                          self.expected_report())

    @rule()
    def reject_credentials(self):
        """Проверить отказ в доступе при неверном пароле."""
        client = ApiClient(self.url, password="wrong")
        with unittest.TestCase().assertRaises(HTTPError) as caught:
            client.api_fetch_entity()
        assert caught.exception.code == HTTPStatus.UNAUTHORIZED
        assert "Basic" in caught.exception.headers["WWW-Authenticate"]

    @rule()
    def reject_invalid_data(self):
        """Проверить ответы на неверные маршруты и параметры."""
        requests = [
            ("GET", "/missing", {}),
            ("POST", "/api/update/entity", {"identifier": "9999"}),
            ("POST", "/api/submit/result", {}),
            ("POST", "/api/update/entity", {"identifier": "0", "bad": "x"}),
        ]
        for method, path, fields in requests:
            with unittest.TestCase().assertRaises(HTTPError) as caught:
                self.client.call(method, path, fields)
            assert caught.exception.code == HTTPStatus.BAD_REQUEST
        with unittest.TestCase().assertRaises(HTTPError) as caught:
            self.client.api_submit_command(9999, argument="x")
        assert caught.exception.code == HTTPStatus.BAD_REQUEST

    @rule()
    def check_time_boundary(self):
        """Проверить, что старая сущность не попадает в отчёт."""
        created = int(time.time()) - 361
        expected = {"identifier": str(len(self.entities)),
                    "created": str(created), "locale": "old",
                    "user_agent": "old"}
        actual = self.client.api_submit_entity(
            locale="old", user_agent="old", created=created,
        )
        self.check_record(actual, expected)
        self.entities.append(expected)
        self.fetch_report()

    @rule()
    def reopen_storage(self):
        """Открыть хранилище заново и проверить сохранённые сущности."""
        self.store.close()
        self.store = self.store_class(self.path)
        self.server.store = self.store
        self.server.jobs.store = self.store
        self.fetch_entity()

    @invariant()
    def persisted_entities(self):
        """Проверять сохранённые сущности между шагами сценария."""
        self.fetch_entity()


TestFileHttp = HttpMachine.TestCase
TestFileHttp.settings = settings(
    max_examples=5, stateful_step_count=10, deadline=None,
)
