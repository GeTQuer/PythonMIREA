import json
import threading
import time
from pathlib import Path


RECENT_SECONDS = 360
DEFAULTS = {
    "entity": {"locale": "", "user_agent": ""},
    "command": {
        "argument": "", "entity": 0, "tags": "", "status": "queued",
        "started": 0,
    },
    "result": {
        "response": "", "status": "", "error": "", "command": 0,
        "cache_hit": 0, "duration": 0,
    },
}


def normalize(table, fields):
    defaults = {**DEFAULTS[table], "created": int(time.time())}
    unknown = fields.keys() - defaults.keys()
    if unknown:
        raise ValueError(f"Неизвестные поля: {sorted(unknown)}")
    converted = {}
    for name, value in fields.items():
        converted[name] = type(defaults[name])(value)
    return converted


def report(entities, commands, now):
    rows = []
    for entity in entities:
        if entity["created"] < now - RECENT_SECONDS:
            continue
        arguments = [
            command["argument"] for command in commands
            if command["entity"] == entity["identifier"]
        ] or [None]
        for argument in arguments:
            row = {"argument": argument, "locale": entity["locale"],
                   "user_agent": entity["user_agent"]}
            if row not in rows:
                rows.append(row)
    return rows


class FileStore:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.tables = {name: [] for name in DEFAULTS}
        if self.path.exists():
            self.tables = json.loads(self.path.read_text(encoding="utf-8"))

    def save(self):
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.tables), encoding="utf-8")
        temporary.replace(self.path)

    def fetch(self, table, fields=None):
        with self.lock:
            return [dict(row) for row in self.tables[table]
                    if all(str(row[key]) == str(value)
                           for key, value in (fields or {}).items())]

    def create(self, table, fields):
        with self.lock:
            fields = normalize(table, fields)
            self.validate_link(table, fields)
            row = {**DEFAULTS[table], "created": int(time.time()), **fields}
            row["identifier"] = len(self.tables[table])
            self.tables[table].append(row)
            self.save()
            return dict(row)

    def validate_link(self, table, fields):
        links = {"command": "entity", "result": "command"}
        link = links.get(table)
        if link and link in fields:
            if not self.fetch(link, {"identifier": fields[link]}):
                raise ValueError("Связанная запись не найдена")

    def update(self, table, identifier, fields):
        with self.lock:
            fields = normalize(table, fields)
            self.validate_link(table, fields)
            found = self.fetch(table, {"identifier": identifier})
            if not found:
                raise ValueError("Запись не найдена")
            row = self.tables[table][int(identifier)]
            row.update(fields)
            self.save()
            return dict(row)

    def get_report(self):
        with self.lock:
            return report(self.fetch("entity"), self.fetch("command"),
                          int(time.time()))

    def close(self):
        pass
