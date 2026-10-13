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
