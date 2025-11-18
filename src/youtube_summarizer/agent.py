from google.adk.agents.llm_agent import Agent
import re
import os
import google.generativeai as genai
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, parse_qs

# Настраиваем API-ключ при загрузке модуля
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
else:
    print("ВНИМАНИЕ: Ключ GEMINI_API_KEY не найден в переменных окружения.")

def get_youtube_transcript(url: str) -> dict:
    """
    Принимает URL YouTube-видео и извлекает транскрипт, делая прямые запросы.
    """
    try:
        video_id = parse_qs(urlparse(url).query).get('v')[0]
        if not video_id:
            return {"error": "Не удалось извлечь ID видео."}

        # Получаем информацию о видео для доступа к транскриптам
        video_info_url = f"https://www.youtube.com/watch?v={video_id}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(video_info_url, headers=headers)

        if response.status_code != 200:
            return {"error": f"Не удалось получить информацию о видео. Статус: {response.status_code}"}

        # Ищем URL для транскриптов в теле HTML
        match = re.search(r'"captionTracks":(\[.*?\])', response.text)
        if not match:
            return {"error": "Транскрипты для этого видео не найдены."}

        caption_tracks = eval(match.group(1).replace("true", "True").replace("false", "False"))

        # Находим URL для английского или русского транскрипта
        transcript_url = None
        for track in caption_tracks:
            if track['languageCode'] in ('en', 'ru'):
                transcript_url = track['baseUrl']
                break

        if not transcript_url:
            return {"error": "Подходящий транскрипт (en/ru) не найден."}

        # Загружаем и парсим XML транскрипта
        transcript_response = requests.get(transcript_url, headers=headers)
        root = ET.fromstring(transcript_response.content)

        # Собираем текст
        transcript_text = " ".join([elem.text for elem in root.findall('text')])

        return {"title": video_id, "transcript": transcript_text.replace("\n", " ")}

    except Exception as e:
        return {"error": f"Произошла непредвиденная ошибка: {str(e)}"}


def summarize_transcript(transcript: str) -> dict:
    """
    Принимает полный текст транскрипта, обрабатывает его по частям и создает
    структурированное саммари на русском языке.
    """
    model = genai.GenerativeModel('models/gemini-pro-latest')

    try:
        text_chunks = [transcript[i:i+15000] for i in range(0, len(transcript), 15000)]
        key_points = []

        for chunk in text_chunks:
            prompt = f"""
            Проанализируй этот фрагмент транскрипта видео и извлеки из него только самые главные, ключевые идеи в виде списка. Будь кратким и по существу.
            Фрагмент: "{chunk}"
            """
            response = model.generate_content(prompt)
            key_points.append(response.text)

        combined_points = "\n".join(key_points)

        final_prompt = f"""
        На основе этих ключевых тезисов со всего видео, создай одно детальное и структурированное саммари на русском языке в формате Markdown.
        Саммари должно иметь следующую структуру:
        - Заголовок `# Ключевые идеи`.
        - Список основных идей с кратким описанием каждой.
        - Заголовок `# Цитаты` (если в тезисах есть что-то похожее на яркие цитаты).
        - Заголовок `# Вывод` с коротким (2-3 предложения) общим итогом.

        Ключевые тезисы: "{combined_points}"
        """
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

root_agent = Agent(
    model='gemini-pro',
    name='youtube_summarizer',
    description="Создает структурированное саммари YouTube-видео и сохраняет его в .md файл.",
    instruction="""Ты — продвинутый ассистент для анализа видео.
1. Получи от пользователя ссылку на YouTube-видео.
2. Используй инструмент `get_youtube_transcript` для получения транскрипта и названия видео. Если произошла ошибка, сообщи о ней пользователю.
3. Используй инструмент `summarize_transcript`, передав в него полученный текст транскрипта.
4. Используй инструмент `save_summary_to_file`, чтобы сохранить готовое саммари в файл. В качестве `title` передай название видео, в `summary` — результат работы `summarize_transcript`.
5. Сообщи пользователю, что задача выполнена и файл сохранен.
""",
    tools=[get_youtube_transcript, summarize_transcript, save_summary_to_file],
)
