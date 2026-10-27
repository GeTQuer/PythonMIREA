import argparse
import shutil
import subprocess
from pathlib import Path


def get_ffmpeg():
    """Найти FFmpeg в PATH или в пакете imageio-ffmpeg."""
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def extract_audio(source, destination):
    """Проверить пути и извлечь звук из MP4 в OGG с помощью FFmpeg."""
    source = Path(source).resolve()
    destination = Path(destination).resolve()
    if source.suffix.lower() != ".mp4" or not source.is_file():
        raise ValueError("Входной файл должен быть существующим MP4")
    if destination.suffix.lower() != ".ogg":
        raise ValueError("Выходной файл должен иметь расширение OGG")
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [get_ffmpeg(), "-y", "-v", "error", "-i", str(source),
         "-vn", "-c:a", "libvorbis", str(destination)],
        check=True,
        capture_output=True,
    )
    return str(destination)


def demonstrate():
    """Создать три примера MP4 и преобразовать их в OGG."""
    directory = Path("data/examples")
    directory.mkdir(parents=True, exist_ok=True)
    for frequency in (220, 440, 880):
        source = directory / f"tone_{frequency}.mp4"
        subprocess.run(
            [get_ffmpeg(), "-y", "-v", "error", "-f", "lavfi", "-i",
             "sine=frequency=" + str(frequency) + ":duration=1",
             "-c:a", "aac",
             str(source)],
            check=True,
        )
        print(extract_audio(source, source.with_suffix(".ogg")))


def main():
    """Разобрать аргументы и запустить преобразование или демонстрацию."""
    parser = argparse.ArgumentParser(description="Извлечение MP4 в OGG")
    parser.add_argument("source", nargs="?")
    parser.add_argument("destination", nargs="?")
    parser.add_argument("--demo", action="store_true")
    arguments = parser.parse_args()
    if arguments.demo:
        demonstrate()
        return
    if not arguments.source or not arguments.destination:
        parser.error("Укажите входной MP4 и выходной OGG")
    print(extract_audio(arguments.source, arguments.destination))


if __name__ == "__main__":
    main()
