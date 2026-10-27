import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


class Jobs:
    """Выполнять команды преобразования в фоновом потоке."""

    def __init__(self, store, test_mode):
        """Сохранить хранилище и создать очередь с одним работником."""
        self.store = store
        self.test_mode = test_mode
        self.pool = ThreadPoolExecutor(max_workers=1)

    def submit(self, command):
        """Поставить задачу в очередь или создать тестовый результат."""
        if self.test_mode:
            self.store.create("result", {
                "command": command["identifier"], "status": "test",
                "response": "test mode",
            })
            return
        self.pool.submit(self.execute, command)

    def execute(self, command):
        """Запустить утилиту, сохранить результат и изменить статус."""
        started = int(time.time())
        identifier = command["identifier"]
        self.store.update("command", identifier,
                          {"status": "running", "started": started})
        fields = {"command": identifier, "status": "done"}
        try:
            paths = json.loads(command["argument"])
            process = subprocess.run(
                [sys.executable, str(Path(__file__).with_name("audio.py")),
                 paths["input"], paths["output"]],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=600,
            )
            fields.update(self.read_process(process))
        except (ValueError, KeyError, OSError,
                subprocess.TimeoutExpired) as exc:
            fields.update(status="error", error=str(exc))
        fields["duration"] = int(time.time()) - started
        self.store.create("result", fields)
        self.store.update("command", identifier, {"status": fields["status"]})

    def read_process(self, process):
        """Получить путь результата или сообщение об ошибке процесса."""
        if process.returncode:
            return {"status": "error", "error": process.stderr.strip()}
        return {"response": process.stdout.strip()}

    def close(self):
        """Дождаться завершения задач и закрыть очередь."""
        self.pool.shutdown(wait=True)
