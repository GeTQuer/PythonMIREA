import datetime
import json
import socket
import socketserver
import sys


RECENT_SECONDS = 6 * 60

entities = []
commands = []
results = []


def get_next_id(table: list) -> int:
    if len(table) == 0:
        return 0
    record = max(table, key=lambda item: item["identifier"])
    return record["identifier"] + 1


def get_by_id(table: list, identifier: int) -> dict:
    for record in table:
        if record["identifier"] == identifier:
            return record
    raise ValueError(f"Запись {identifier} не найдена")


def update_record(record: dict, fields: dict) -> dict:
    for name, value in fields.items():
        if value is not None:
            record[name] = value
    return record


def create_entity(locale=None, user_agent=None, created=None) -> dict:
    entity = {
        "identifier": get_next_id(entities),
        "created": created or int(datetime.datetime.now().timestamp()),
        "locale": locale,
        "user_agent": user_agent,
    }
    entities.append(entity)
    return entity


def get_all_entities() -> list[dict]:
    return entities


def edit_entity(identifier, locale=None, user_agent=None) -> dict:
    entity = get_by_id(entities, identifier)
    fields = {"locale": locale, "user_agent": user_agent}
    return update_record(entity, fields)


def create_command(
    entity,
    argument=None,
    tags=None,
    status=None,
    started=None,
    created=None,
) -> dict:
    get_by_id(entities, entity)
    command = {
        "identifier": get_next_id(commands),
        "created": created or int(datetime.datetime.now().timestamp()),
        "argument": argument,
        "entity": entity,
        "tags": tags,
        "status": status,
        "started": started,
    }
    commands.append(command)
    return command


def get_all_commands() -> list[dict]:
    return commands


def edit_command(
    identifier,
    argument=None,
    entity=None,
    tags=None,
    status=None,
    started=None,
) -> dict:
    if entity is not None:
        get_by_id(entities, entity)
    command = get_by_id(commands, identifier)
    fields = {
        "argument": argument,
        "entity": entity,
        "tags": tags,
        "status": status,
        "started": started,
    }
    return update_record(command, fields)


def create_result(
    command,
    response=None,
    status=None,
    error=None,
    cache_hit=None,
    duration=None,
) -> dict:
    get_by_id(commands, command)
    result = {
        "identifier": get_next_id(results),
        "created": int(datetime.datetime.now().timestamp()),
        "response": response,
        "status": status,
        "error": error,
        "command": command,
        "cache_hit": cache_hit,
        "duration": duration,
    }
    results.append(result)
    return result


def get_all_results() -> list[dict]:
    return results


def edit_result(
    identifier,
    response=None,
    status=None,
    error=None,
    command=None,
    cache_hit=None,
    duration=None,
) -> dict:
    if command is not None:
        get_by_id(commands, command)
    result = get_by_id(results, identifier)
    fields = {
        "response": response,
        "status": status,
        "error": error,
        "command": command,
        "cache_hit": cache_hit,
        "duration": duration,
    }
    return update_record(result, fields)


def get_recent_commands(now=None) -> list[dict]:
    current_time = now or int(datetime.datetime.now().timestamp())
    selected = []
    for entity in entities:
        if entity["created"] < current_time - RECENT_SECONDS:
            continue
        match_found = False
        for command in commands:
            if entity["identifier"] == command["entity"]:
                selected.append({
                    "argument": command["argument"],
                    "locale": entity["locale"],
                    "user_agent": entity["user_agent"],
                })
                match_found = True
        if not match_found:
            selected.append({
                "argument": None,
                "locale": entity["locale"],
                "user_agent": entity["user_agent"],
            })
    return selected


def repl():
    while True:
        try:
            choice = input()
            match choice:
                case "create_entity":
                    print(create_entity("ru", "Chrome"))
                case "get_all_entities":
                    print(get_all_entities())
                case "edit_entity":
                    print(edit_entity(0, locale="en"))
                case "create_command":
                    print(create_command(0, argument="ping"))
                case "get_all_commands":
                    print(get_all_commands())
                case "edit_command":
                    print(edit_command(0, status="done"))
                case "create_result":
                    print(create_result(0, response="pong"))
                case "get_all_results":
                    print(get_all_results())
                case "edit_result":
                    print(edit_result(0, status="ok"))
                case "get_recent_commands":
                    print(get_recent_commands())
                case "exit":
                    return
                case _:
                    raise ValueError("Неизвестная команда")
        except (TypeError, ValueError) as error:
            print(error)


FUNCTIONS = (
    create_entity,
    get_all_entities,
    edit_entity,
    create_command,
    get_all_commands,
    edit_command,
    create_result,
    get_all_results,
    edit_result,
    get_recent_commands,
)


def receive_exact(connection, size):
    data = b""
    while len(data) < size:
        part = connection.recv(size - len(data))
        if not part:
            raise ValueError("Соединение закрыто")
        data += part
    return data


def encode_message(code, body, code_size):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    return (
        code.to_bytes(code_size, "little")
        + len(data).to_bytes(5, "little")
        + data
    )


def receive_message(connection, code_size):
    code = int.from_bytes(receive_exact(connection, code_size), "little")
    body_size = int.from_bytes(receive_exact(connection, 5), "little")
    body = receive_exact(connection, body_size).decode("utf-8")
    return code, json.loads(body)


class RequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        code = 255
        try:
            code, arguments = receive_message(self.request, 2)
            if code >= len(FUNCTIONS):
                raise ValueError("Неизвестный код операции")
            result = FUNCTIONS[code](**arguments)
            response = {"result": result}
        except (TypeError, ValueError) as error:
            response = {"error": str(error)}
        response_code = code if code < len(FUNCTIONS) else 255
        self.request.sendall(encode_message(response_code, response, 1))
        print(json.dumps(response, ensure_ascii=False), flush=True)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def run_server(host="127.0.0.1", port=8080):
    with Server((host, port), RequestHandler) as server:
        print(f"RPC server started on {host}:{port}")
        server.serve_forever()


class RpcClient:
    def __init__(self, host="127.0.0.1", port=8080):
        self.host = host
        self.port = port

    def call(self, code, arguments):
        request = encode_message(code, arguments, 2)
        with socket.create_connection((self.host, self.port)) as connection:
            connection.sendall(request)
            response_code, response = receive_message(connection, 1)
        if response_code != code:
            raise ValueError("Неверный код операции в ответе")
        if "error" in response:
            raise ValueError(response["error"])
        return response["result"]

    def create_entity(self, locale=None, user_agent=None, created=None):
        return self.call(0, {
            "locale": locale,
            "user_agent": user_agent,
            "created": created,
        })

    def get_all_entities(self):
        return self.call(1, {})

    def edit_entity(self, identifier, locale=None, user_agent=None):
        return self.call(2, {
            "identifier": identifier,
            "locale": locale,
            "user_agent": user_agent,
        })

    def create_command(
        self,
        entity,
        argument=None,
        tags=None,
        status=None,
        started=None,
        created=None,
    ):
        return self.call(3, {
            "entity": entity,
            "argument": argument,
            "tags": tags,
            "status": status,
            "started": started,
            "created": created,
        })

    def get_all_commands(self):
        return self.call(4, {})

    def edit_command(
        self,
        identifier,
        argument=None,
        entity=None,
        tags=None,
        status=None,
        started=None,
    ):
        return self.call(5, {
            "identifier": identifier,
            "argument": argument,
            "entity": entity,
            "tags": tags,
            "status": status,
            "started": started,
        })

    def create_result(
        self,
        command,
        response=None,
        status=None,
        error=None,
        cache_hit=None,
        duration=None,
    ):
        return self.call(6, {
            "command": command,
            "response": response,
            "status": status,
            "error": error,
            "cache_hit": cache_hit,
            "duration": duration,
        })

    def get_all_results(self):
        return self.call(7, {})

    def edit_result(self, identifier, **fields):
        return self.call(8, {"identifier": identifier, **fields})

    def get_recent_commands(self, now=None):
        return self.call(9, {"now": now})


def demonstrate(client):
    entity = client.create_entity("ru", "Chrome")
    print(client.get_all_entities())
    print(client.edit_entity(entity["identifier"], locale="en"))
    command = client.create_command(entity["identifier"], argument="ping")
    print(client.get_all_commands())
    print(client.edit_command(command["identifier"], status="done"))
    result = client.create_result(command["identifier"], response="pong")
    print(client.get_all_results())
    print(client.edit_result(result["identifier"], status="ok"))
    print(client.get_recent_commands())


def run_demo():
    demonstrate(RpcClient())


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "repl"
    if mode == "repl":
        repl()
    elif mode == "server":
        run_server()
    elif mode == "demo":
        run_demo()


if __name__ == "__main__":
    main()
