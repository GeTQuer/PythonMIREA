# Практика №2, вариант 12

Тема: асинхронное извлечение OGG-аудио из MP4.
Практика №1 сохранена в src/main.py и tests/test_main.py.

## Этап 1

Установка: `python -m pip install -r requirements.txt`.
FFmpeg берётся из PATH или пакета imageio-ffmpeg.

`run.bat audio input.mp4 output.ogg` читает MP4 и записывает OGG.
`run.bat audio --demo` генерирует три MP4 с частотами 220, 440, 880 Гц
и преобразует каждый в OGG. Файлы находятся в data/examples и не
попадают в Git. Требуется аудиодорожка; видео не переносится в OGG.
FFmpeg запускается списком аргументов без shell.

## Этап 2

`run.bat http` запускает API на http://127.0.0.1:8081.
Настройки в config.ini: host, port, username, password, database,
test_mode. По умолчанию логин и пароль student; замените их для своего
запуска. Basic-аутентификация требует HTTPS вне локального компьютера.
При неверных данных авторизации сервер возвращает 401 и
WWW-Authenticate. Успех: 200, ошибки параметров: 400. Ответы всегда XML.

| Метод | Маршрут | Вход |
|---|---|---|
| POST | /api/submit/entity | XML locale, user_agent, created |
| GET | /api/fetch/entity | Фильтры в query, например identifier |
| POST | /api/update/entity | identifier и изменяемые поля в query |
| POST | /api/submit/command | XML entity, argument, tags, status, started |
| GET | /api/fetch/command/:entity | ID сущности в пути, фильтры в query |
| POST | /api/update/command | identifier и изменяемые поля в query |
| GET | /api/fetch/result/:command | ID команды в пути, фильтры в query |
| GET | /api/fetch/report | Без параметров |

created задаётся в Unix-секундах, по умолчанию текущее время.
Report: последние 6 минут, включая границу, левое соединение Entity
с Command; поля argument, locale, user_agent; одинаковые строки убираются.
При отсутствии команды argument имеет XML-атрибут null="true".

Argument команды — JSON-строка с input и output, путями MP4 и OGG.
API принимает задачи для локальных файлов сервера. Файлы предварительно
помещаются на компьютер сервера; отдельного маршрута загрузки в задании нет.
Выполнение происходит в фоне, одной задачей за раз. Статусы команды:
queued, running, done, error. Result содержит response (путь OGG), error
(сообщение), status, cache_hit (0), duration (секунды). started — Unix-время.
Задачи выполняются через subprocess и утилиту этапа 1, timeout 600 секунд.
В test_mode=true FFmpeg не запускается, Result содержит status=test,
response=test mode. Очередь в памяти: незавершённые задачи при остановке
сервера автоматически не возобновляются.

```python
import json
from src.http_client import ApiClient

api = ApiClient("http://127.0.0.1:8081")
entity = api.api_submit_entity(locale="ru", user_agent="Python")
command = api.api_submit_command(
    entity["identifier"],
    argument=json.dumps({"input": "data/examples/tone_440.mp4",
                         "output": "data/output.ogg"}),
)
print(api.api_fetch_result(command["identifier"]))
```

Повторяйте fetch_result до появления результата. Клиент возвращает строки
XML, целые поля при необходимости преобразуются через int.
Методы ApiClient названы по маршрутам, с заменой / на _.
Результаты создания и изменения — словарь; поиск и отчёт — список словарей.

`run.bat test-http` запускает только Hypothesis MBT через HTTP-клиент,
отчёт ветвей Coverage и PEP8. HTML: htmlcov/http/index.html.
Правила раздельные, поэтому при ошибке выводится цепочка операций.
initialize гарантирует вызов всех восьми обработчиков даже в коротком
сценарии. Проверяются неверная авторизация, обновления, связи, XML-символы,
отчёт, старая сущность, повторное открытие файлового хранилища.
Хранилище этапа 2 — атомарно заменяемый JSON-файл, операции защищены lock.

## Этап 3

По умолчанию config.ini использует backend=sqlite и data/api.sqlite.
Для реализации этапа 2 задайте backend=file, database=data/api.json.
SQLite использует PonyORM, три таблицы и настоящие внешние ключи:
Command.entity → Entity.identifier, Result.command → Command.identifier.
Каждая операция выполняется в db_session; записи фиксируются транзакцией.
Поля и HTTP-интерфейс обоих хранилищ одинаковы. Автоматической миграции
между JSON и SQLite нет; файлы хранят независимые данные.

`run.bat test-sqlite` запускает те же правила Hypothesis на SQLite,
строит отчёт ветвей и HTML в htmlcov/sqlite/index.html.
Оба набора включают повторное открытие базы с проверкой сохранённых данных.
`run.bat test` запускает все тесты, включая сохранённую практику №1.

Исходники: audio.py — CLI, http_api.py — сервер, http_client.py — клиент,
xml_api.py — XML, jobs.py — очередь задач, storage.py — файловая модель,
sqlite_store.py — PonyORM. Tests: test_http.py и test_sqlite_http.py.
В коде нет комментариев; функции ограничены 40 строками, аргументы — 7,
цикломатическая и когнитивная сложность — не более 10.

## Результаты проверки

Три MP4-примера успешно преобразованы в OGG. Проверены реальные фоновые
задачи через HTTP с JSON-хранилищем и SQLite, включая сохранение Result
после повторного открытия базы. Эти ручные интеграционные проверки не
включены в отчёты покрытия MBT.
Отдельные прогоны Hypothesis покрывают все восемь обработчиков, клиент —
100%; слой SQLite — 100%, файловый слой — до 99%.
Общее покрытие отдельных наборов API около 86%; ветви реального FFmpeg
не выполняются в тестовом режиме. HTML-отчёт показывает оставшиеся ветви.
