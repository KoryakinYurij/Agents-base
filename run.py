import argparse
import os
import sys
from dotenv import load_dotenv
import google.generativeai as genai

# Добавляем путь к папке с нашей "библиотекой"
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'youtube_summarizer'))

# Теперь, когда путь добавлен, импортируем функции
from functions import get_youtube_transcript, summarize_transcript, save_summary_to_file

def main():
    """
    Основная функция для запуска процесса суммирования видео YouTube.
    """
    # 1. Загружаем и настраиваем API-ключ из .env файла
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ Ошибка: Ключ GEMINI_API_KEY не найден.")
        print("Пожалуйста, создайте файл .env в корневой папке проекта и добавьте в него строку:")
        print('GEMINI_API_KEY="ВАШ_КЛЮЧ"')
        sys.exit(1) # Завершаем работу, если ключ не найден

    try:
        genai.configure(api_key=api_key)
        print("✅ API-ключ успешно настроен.")
    except Exception as e:
        print(f"❌ Ошибка при конфигурации API-ключа: {e}")
        sys.exit(1)

    # 2. Настраиваем парсер для получения URL из командной строки
    parser = argparse.ArgumentParser(
        description="Скрипт для создания саммари YouTube-видео.",
        epilog="Пример использования: python run.py \"https://www.youtube.com/watch?v=...\""
    )
    parser.add_argument("url", type=str, help="Полный URL видео на YouTube.")
    args = parser.parse_args()
    video_url = args.url

    print(f"\n🚀 Начинаю обработку видео: {video_url}")

    # --- НАЧАЛО КОНВЕЙЕРА ---

    # Шаг 1: Получение транскрипта
    print("Этап 1: Получение транскрипта...")
    transcript_data = get_youtube_transcript(video_url)
    if "error" in transcript_data:
        print(f"❌ Ошибка на этапе 1: {transcript_data['error']}")
        sys.exit(1)

    video_title = transcript_data['title']
    transcript_text = transcript_data['transcript']
    print("✅ Транскрипт и название видео успешно получены.")

    # Шаг 2: Создание саммари
    print("Этап 2: Создание саммари (это может занять некоторое время)...")
    summary_data = summarize_transcript(transcript_text)
    if "error" in summary_data:
        print(f"❌ Ошибка на этапе 2: {summary_data['error']}")
        sys.exit(1)

    summary_text = summary_data['summary']
    print("✅ Саммари успешно создано.")

    # Шаг 3: Сохранение файла
    print("Этап 3: Сохранение результата в файл...")
    save_result = save_summary_to_file(video_title, summary_text)
    if "error" in save_result:
        print(f"❌ Ошибка на этапе 3: {save_result['error']}")
        sys.exit(1)

    # --- КОНЕЦ КОНВЕЙЕРА ---

    print(f"\n🎉 Все готово! {save_result['message']}")

if __name__ == "__main__":
    main()
