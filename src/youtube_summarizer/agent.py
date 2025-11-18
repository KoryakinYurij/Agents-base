from google.adk.agents.llm_agent import Agent
from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp
import re
import os
import google.generativeai as genai

# Настраиваем API-ключ при загрузке модуля
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
else:
    print("ВНИМАНИЕ: Ключ GEMINI_API_KEY не найден в переменных окружения.")

def get_youtube_transcript(url: str) -> dict:
    """
    Принимает URL YouTube-видео, извлекает его название и полный текст транскрипта.

    Args:
        url: Ссылка на YouTube-видео.

    Returns:
        Словарь с ключами 'title' (название видео) и 'transcript' (текст транскрипта).
        В случае ошибки возвращает словарь с ключом 'error'.
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
        # Используем yt-dlp для получения названия видео
        ydl_opts = {'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'Без названия')

        # Получаем транскрипт
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'en-US'])
        transcript_text = " ".join([item['text'] for item in transcript_list])

        return {"title": video_title, "transcript": transcript_text}

    except Exception as e:
        return {"error": f"Произошла ошибка при получении данных: {str(e)}"}

def summarize_transcript(transcript: str) -> dict:
    """
    Принимает полный текст транскрипта, обрабатывает его по частям и создает
    структурированное саммари на русском языке.

    Args:
        transcript: Текст транскрипта.

    Returns:
        Словарь с ключом 'summary' (готовое саммари в формате Markdown).
        В случае ошибки возвращает словарь с ключом 'error'.
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

    Args:
        title: Название видео, которое будет использовано для имени файла.
        summary: Текст саммари.

    Returns:
        Словарь с сообщением об успехе или ошибке.
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
