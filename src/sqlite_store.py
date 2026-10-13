import threading
import time
from pathlib import Path

from pony.orm import Database, Optional, PrimaryKey, Required, Set
from pony.orm import db_session, flush

from src.storage import DEFAULTS, normalize, report


def define_entity(database):
    class Participant(database.Entity):
        _table_ = "Entity"
        identifier = PrimaryKey(int)
        created = Required(int)
        locale = Optional(str, default="", autostrip=False)
        user_agent = Optional(str, default="", autostrip=False)
        commands = Set("Command")
    return Participant


def define_command(database):
    class Command(database.Entity):
        identifier = PrimaryKey(int)
        created = Required(int)
        argument = Optional(str, default="", autostrip=False)
        entity = Required("Participant")
        tags = Optional(str, default="", autostrip=False)
        status = Optional(str, default="queued", autostrip=False)
        started = Required(int, default=0)
        results = Set("Result")
    return Command


def define_result(database):
    class Result(database.Entity):
        identifier = PrimaryKey(int)
        created = Required(int)
        response = Optional(str, default="", autostrip=False)
        status = Optional(str, default="", autostrip=False)
        error = Optional(str, default="", autostrip=False)
        command = Required("Command")
        cache_hit = Required(int, default=0)
        duration = Required(int, default=0)
    return Result


class SqliteStore:
    def __init__(self, path):
        self.lock = threading.RLock()
        path = Path(path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.database = Database()
        self.tables = {
            "entity": define_entity(self.database),
            "command": define_command(self.database),
            "result": define_result(self.database),
        }
        self.database.bind(provider="sqlite", filename=str(path),
                           create_db=True)
        self.database.generate_mapping(create_tables=True)

    def serialize(self, table, record):
        row = {name: getattr(record, name) for name in DEFAULTS[table]}
        for name in ("entity", "command"):
            if name in row:
                row[name] = row[name].identifier
        return {"identifier": record.identifier,
                "created": record.created, **row}

    def fetch(self, table, fields=None):
        with self.lock, db_session:
            entity = self.tables[table]
            rows = [self.serialize(table, record)
                    for record in entity.select().order_by(entity.identifier)]
            return [row for row in rows
                    if all(str(row[key]) == str(value)
                           for key, value in (fields or {}).items())]

    def prepare(self, table, fields):
        fields = normalize(table, fields)
        links = {"command": "entity", "result": "command"}
        name = links.get(table)
        if name and name in fields:
            related = self.tables[name].get(identifier=fields[name])
            if related is None:
                raise ValueError("Связанная запись не найдена")
            fields[name] = related
        return fields

    def create(self, table, fields):
        with self.lock, db_session:
            defaults = {**DEFAULTS[table], "created": int(time.time())}
            values = self.prepare(table, {**defaults, **fields})
            entity = self.tables[table]
            record = entity(identifier=entity.select().count(), **values)
            flush()
            return self.serialize(table, record)

    def update(self, table, identifier, fields):
        with self.lock, db_session:
            entity = self.tables[table]
            record = entity.get(identifier=int(identifier))
            if record is None:
                raise ValueError("Запись не найдена")
            record.set(**self.prepare(table, fields))
            return self.serialize(table, record)

    def get_report(self):
        with self.lock, db_session:
            return report(self.fetch("entity"), self.fetch("command"),
                          int(time.time()))

    def close(self):
        self.database.disconnect()
