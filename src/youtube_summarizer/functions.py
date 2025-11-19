import yt_dlp
import re
import os
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi

# Обратите внимание: загрузка .env и конфигурация genai теперь происходит
# в основном скрипте run.py. Этот файл - просто библиотека функций.

def get_youtube_transcript(url: str) -> dict:
    """
    Принимает URL YouTube-видео, извлекает его название и полный текст транскрипта.
    """
    video_id = None
    patterns = [
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})',
        r'(?:https?:\/\/)?(?:www\.)?youtu\.be\/([a-zA-Z0-9_-]{11})',
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            break

    if not video_id:
        return {"error": "Не удалось извлечь ID видео из ссылки. Убедитесь, что ссылка корректна."}

    try:
        ydl_opts = {'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'Без названия')

        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'en-US', 'ru'])
        transcript_text = " ".join([item['text'] for item in transcript_list])

        return {"title": video_title, "transcript": transcript_text}

    except Exception as e:
        return {"error": f"Произошла ошибка при получении данных: {str(e)}"}


def summarize_transcript(transcript: str) -> dict:
    """
    Принимает полный текст транскрипта и создает его саммари.
    """
    if not os.getenv("GEMINI_API_KEY"):
         return {"error": "Ключ GEMINI_API_KEY не был загружен. Убедитесь, что .env файл настроен правильно."}

    model = genai.GenerativeModel('models/gemini-pro-latest')

    try:
        # Простая проверка длины транскрипта, чтобы избежать лишних вызовов API
        if len(transcript) < 100: # Условная длина, можно настроить
            return {"summary": "Транскрипт слишком короткий для создания качественного саммари."}

        text_chunks = [transcript[i:i+15000] for i in range(0, len(transcript), 15000)]
        key_points = []

        for chunk in text_chunks:
            prompt = f"Проанализируй этот фрагмент транскрипта видео и извлеки из него только самые главные, ключевые идеи в виде списка. Будь кратким и по существу. Фрагмент: \"{chunk}\""
            response = model.generate_content(prompt)
            key_points.append(response.text)

        combined_points = "\n".join(key_points)

        final_prompt = f"На основе этих ключевых тезисов со всего видео, создай одно детальное и структурированное саммари на русском языке в формате Markdown. Саммари должно иметь следующую структуру:\n- Заголовок `# Ключевые идеи`.\n- Список основных идей с кратким описанием каждой.\n- Заголовок `# Цитаты` (если в тезисах есть что-то похожее на яркие цитаты).\n- Заголовок `# Вывод` с коротким (2-3 предложения) общим итогом.\n\nКлючевые тезисы: \"{combined_points}\""
        final_response = model.generate_content(final_prompt)

        return {"summary": final_response.text}
    except Exception as e:
        return {"error": f"Ошибка при генерации саммари: {str(e)}"}


def save_summary_to_file(title: str, summary: str) -> dict:
    """
    Сохраняет готовое саммари в .md файл.
    """
    try:
        sane_title = re.sub(r'[^\w\s-]', '', title).strip()
        sane_title = re.sub(r'[-\s]+', '-', sane_title)
        filename = f"{sane_title}.md"

        output_dir = "summaries"
        os.makedirs(output_dir, exist_ok=True)

        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(summary)

        return {"status": "success", "message": f"Файл успешно сохранен: {filepath}"}
    except Exception as e:
        return {"error": f"Не удалось сохранить файл: {str(e)}"}
