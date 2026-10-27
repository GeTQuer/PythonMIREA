import argparse
import base64
import configparser
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlsplit
from xml.etree import ElementTree

from src.jobs import Jobs
from src.storage import FileStore
from src.xml_api import encode


OK = 200
UNAUTHORIZED = 401
BAD_REQUEST = 400


class Handler(BaseHTTPRequestHandler):
    """Принимать HTTP-запросы и возвращать XML-ответы."""

    def do_GET(self):
        """Передать GET-запрос общему обработчику."""
        self.handle_api()

    def do_POST(self):
        """Передать POST-запрос общему обработчику."""
        self.handle_api()

    def log_message(self, format, *args):
        """Отключить стандартный вывод запросов в консоль."""
        pass

    def handle_api(self):
        """Проверить авторизацию, обработать запрос и отправить ответ."""
        authorization = self.headers.get("Authorization", "")
        if not hmac.compare_digest(authorization, self.server.authorization):
            self.respond(UNAUTHORIZED, {"error": "Unauthorized"})
            return
        try:
            address = urlsplit(self.path)
            fields = dict(parse_qsl(address.query, keep_blank_values=True))
            value = self.dispatch(address.path, fields)
            self.respond(OK, value)
        except (ValueError, KeyError, TypeError, IndexError,
                ElementTree.ParseError) as exc:
            self.respond(BAD_REQUEST, {"error": str(exc)})

    def dispatch(self, path, fields):
        """Выбрать операцию по методу и маршруту запроса."""
        parts = path.strip("/").split("/")
        if len(parts) < 3:
            raise ValueError("Неизвестный маршрут")
        prefix, action, table = parts[:3]
        if prefix != "api":
            raise ValueError("Неизвестный маршрут")
        if self.command == "GET" and action == "fetch":
            if table == "report":
                return self.server.store.get_report()
            links = {"command": "entity", "result": "command"}
            if table in links:
                fields[links[table]] = parts[3]
            return self.server.store.fetch(table, fields)
        if self.command != "POST" or table not in ("entity", "command"):
            raise ValueError("Неизвестный маршрут")
        if action == "update":
            identifier = fields.pop("identifier")
            return self.server.store.update(table, identifier, fields)
        if action == "submit":
            return self.submit(table)
        raise ValueError("Неизвестный маршрут")

    def submit(self, table):
        """Прочитать XML, создать запись и запустить команду в фоне."""
        size = int(self.headers.get("Content-Length", "0"))
        root = ElementTree.fromstring(self.rfile.read(size))
        fields = {item.tag: item.text or "" for item in root}
        record = self.server.store.create(table, fields)
        if table == "command":
            self.server.jobs.submit(record)
        return record

    def respond(self, status, value):
        """Отправить HTTP-статус и XML с результатом или ошибкой."""
        data = encode(value)
        self.send_response(status)
        self.send_header("Content-Type", "application/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        if status == UNAUTHORIZED:
            self.send_header("WWW-Authenticate", 'Basic realm="audio"')
        self.end_headers()
        self.wfile.write(data)


def create_server(settings, store):
    """Создать HTTP-сервер, настроить авторизацию и очередь задач."""
    server = ThreadingHTTPServer((settings["host"], int(settings["port"])),
                                 Handler)
    credentials = ":".join((settings["username"], settings["password"]))
    token = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
    server.authorization = f"Basic {token}"
    server.store = store
    server.jobs = Jobs(store, settings.get("test_mode", "false") == "true")
    return server


def main():
    """Прочитать конфигурацию и запустить HTTP-сервер."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.ini")
    arguments = parser.parse_args()
    config = configparser.ConfigParser()
    config.read(arguments.config, encoding="utf-8")
    settings = config["api"]
    store = FileStore(settings["database"])
    server = create_server(settings, store)
    print("HTTP API:", server.server_address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        server.jobs.close()
        store.close()


if __name__ == "__main__":
    main()
