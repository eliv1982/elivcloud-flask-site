"""
Helper functions for the /chat FAQ-RAG backend endpoint.
"""

from typing import Any

SYSTEM_PROMPT = """\
Ты — ассистент сайта ElivCloud. Отвечаешь на вопросы посетителей.

Правила форматирования:
- Отвечай обычным текстом без Markdown.
- Не используй **жирный**, _курсив_, ### заголовки, таблицы и code fences.
- Для перечислений используй простые строки с дефисом "- " или нумерацию "1. ", "2. " без выделения жирным.
- Делай ответы компактными — они отображаются в небольшом чат-виджете.

Правила содержания:
- Отвечай кратко, спокойно и по делу.
- Используй только предоставленный контекст базы знаний.
- Не выдумывай цены, сроки, гарантии, опыт, клиентов или факты, которых нет в контексте.
- Если информации недостаточно, честно скажи, что не уверен, и предложи оставить заявку через форму контактов или написать в Telegram @elena_shlenskova.
- Не давай юридические, медицинские, финансовые или иные профессиональные консультации как окончательное заключение.
- Если вопрос связан с услугами, кейсами, RAG, MCP, Telegram-ботами, AI-автоматизацией, процессом работы или контактами ElivCloud — отвечай по базе знаний.
- Если вопрос явно не относится к ElivCloud, вежливо верни пользователя к теме сайта.
"""

MAX_HISTORY_MESSAGES = 6
MAX_MESSAGE_LENGTH = 2000


def format_rag_context(results: list[dict]) -> str:
    if not results:
        return "База знаний не вернула релевантных фрагментов по данному вопросу."
    parts = []
    for i, r in enumerate(results, 1):
        parts.append(
            f"[{i}] Источник: {r['source']} | Тип: {r['kind']}\n"
            f"Тема: {r['question']}\n"
            f"Содержание: {r['answer']}"
        )
    return "\n\n".join(parts)


def normalize_chat_history(history: Any) -> list[dict]:
    if not isinstance(history, list):
        return []
    normalized = []
    for item in history:
        if not isinstance(item, dict):
            continue
        role = item.get("role", "")
        content = item.get("content", "")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            normalized.append({"role": role, "content": content.strip()})
    return normalized[-MAX_HISTORY_MESSAGES:]


def build_chat_messages(
    user_message: str,
    rag_context: str,
    history: list[dict],
) -> list[dict]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append(
        {
            "role": "user",
            "content": (
                f"{user_message}\n\n"
                f"---\nКонтекст из базы знаний ElivCloud:\n{rag_context}"
            ),
        }
    )
    return messages
