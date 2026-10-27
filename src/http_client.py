import base64
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.xml_api import decode, request_body


class ApiClient:
    """Отправлять запросы к HTTP API и разбирать XML-ответы."""

    def __init__(self, url, username="student", password="student"):
        """Сохранить адрес сервера и подготовить Basic-авторизацию."""
        self.url = url
        credentials = ":".join((username, password)).encode("utf-8")
        self.authorization = "Basic " + base64.b64encode(credentials).decode()

    def call(self, method, path, fields=None, xml=False):
        """Отправить HTTP-запрос и вернуть записи из XML-ответа."""
        fields = fields or {}
        data = request_body(fields) if xml else None
        query = "" if xml or not fields else "?" + urlencode(fields)
        headers = {"Authorization": self.authorization,
                   "Content-Type": "application/xml"}
        request = Request(self.url + path + query, data=data,
                          headers=headers, method=method)
        with urlopen(request, timeout=10) as response:
            return decode(response.read())

    def api_submit_entity(self, **fields):
        """Создать сущность, передав её поля в XML."""
        return self.call("POST", "/api/submit/entity", fields, xml=True)[0]

    def api_fetch_entity(self, **fields):
        """Найти сущности по параметрам запроса."""
        return self.call("GET", "/api/fetch/entity", fields)

    def api_update_entity(self, identifier, **fields):
        """Изменить сущность по идентификатору."""
        return self.call("POST", "/api/update/entity",
                         {"identifier": identifier, **fields})[0]

    def api_submit_command(self, entity, **fields):
        """Создать команду для указанной сущности."""
        return self.call("POST", "/api/submit/command",
                         {"entity": entity, **fields}, xml=True)[0]

    def api_fetch_command(self, entity, **fields):
        """Найти команды указанной сущности."""
        return self.call("GET", f"/api/fetch/command/{entity}", fields)

    def api_update_command(self, identifier, **fields):
        """Изменить команду по идентификатору."""
        return self.call("POST", "/api/update/command",
                         {"identifier": identifier, **fields})[0]

    def api_fetch_result(self, command, **fields):
        """Получить результаты указанной команды."""
        return self.call("GET", f"/api/fetch/result/{command}", fields)

    def api_fetch_report(self):
        """Получить отчёт по недавним сущностям и их командам."""
        return self.call("GET", "/api/fetch/report")
