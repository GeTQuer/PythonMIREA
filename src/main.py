import datetime
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


if __name__ == "__main__" and sys.argv[-1] == "repl":
    repl()
