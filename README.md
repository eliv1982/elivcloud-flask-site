# ElivCloud Flask Portfolio Site

ElivCloud — личный сайт-портфолио в сфере AI automation, prompt engineering, RAG-ассистентов, Telegram-ботов и AI-инструментов для бизнеса. Сайт доработан как портфолио ElivCloud и содержит реальные AI/RAG/Telegram/MCP/agent кейсы.

## Что реализовано

- Главная страница с hero-блоком
- Описание специализации
- Блок пользы для клиента
- Страница кейсов
- Отдельные страницы кейсов
- Форма контактов
- Простая админка для просмотра заявок
- SQLite database
- Flask, Jinja2, SQLAlchemy, Flask-WTF, Flask-Login
- Bootstrap-based responsive layout

## Позиционирование

Помогаю малому бизнесу, экспертам и небольшим командам сокращать время на повторяющиеся текстовые и клиентские процессы: обращения, отзывы, заявки, документы и базы знаний. Собираю AI-ботов, RAG-ассистентов и простые автоматизации, которые превращают ручную рутину в понятный рабочий процесс.

## Кейсы

1. Customer Review MCP Assistant — AI-ассистент для мониторинга отзывов через MCP-style архитектуру
2. Legal RAG Assistant — RAG-ассистент по юридическим материалам (независимые гарантии)
3. AI Agent Toolbox — локальный AI-агент с набором инструментов на LangChain/Streamlit
4. Weather Teller — Telegram-бот с AI-пояснениями погоды, подписками и сравнением локаций
5. MoodMuse — Telegram-бот для создания персонализированных AI-открыток
6. Open Model Tone Fine-tuning — LoRA fine-tuning открытой русскоязычной модели под спокойный tone of voice

## Структура проекта

```text
elivcloud-site/
├── app.py
├── config.py
├── requirements.txt
├── .env.example
├── templates/
├── static/
├── instance/
└── screenshots/
```

`instance/site.db` создаётся локально и не должен коммититься в репозиторий.

## Локальный запуск

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Адрес приложения:
[http://127.0.0.1:5000](http://127.0.0.1:5000)

## Админка

Адрес:
[http://127.0.0.1:5000/admin/login](http://127.0.0.1:5000/admin/login)

Для локального запуска:
- `ADMIN_USERNAME=admin`
- `ADMIN_PASSWORD=admin123`

Перед публичным деплоем нужно заменить `SECRET_KEY` и `ADMIN_PASSWORD` и хранить их через переменные окружения или `.env`-файл, который не коммитится.

## Переменные окружения

- `SECRET_KEY` — секретный ключ Flask-сессий и CSRF.
- `DATABASE_URL` — строка подключения к базе данных (по умолчанию SQLite в `instance/site.db`).
- `ADMIN_USERNAME` — логин администратора.
- `ADMIN_PASSWORD` — пароль администратора.

## FAQ/RAG chat backend

Сайт содержит POST endpoint `/chat` для FAQ-ассистента на основе FAISS + OpenAI.

### Подготовка

Добавьте в `.env`:

```text
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_CHAT_MODEL=gpt-4o-mini
```

### Построить индекс

```powershell
.\.venv\Scripts\python.exe build_index.py
```

Индекс сохраняется в `data/faiss_index.bin` и `data/faqs_metadata.npy` (gitignored).

### Запустить сайт

```powershell
.\.venv\Scripts\python.exe app.py
```

### Проверить `/chat` через PowerShell

```powershell
$body = @{
  message = "Чем занимается ElivCloud?"
  history = @()
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri "http://127.0.0.1:5000/chat" -Method Post -ContentType "application/json" -Body $body
```

Ответ содержит поля `answer` (текст ответа) и `sources` (список релевантных документов с полями `score`, `source`, `kind`, `question`).

## FAQ/RAG chat widget

Чат-виджет встроен во все публичные страницы сайта (`/`, `/cases`, `/cases/<slug>`, `/contact`).
На `/admin*` страницах виджет не отображается.

- Кнопка в правом нижнем углу открывает окно чата.
- Использует POST `/chat`.
- Передаёт историю диалога (до 6 последних сообщений) в каждом запросе.
- Backend отвечает на основе FAISS/RAG базы знаний из `data/`.
- Реализован на vanilla JS + CSS, без сторонних frontend-зависимостей.

## Деплой

Для публичного деплоя Flask-приложение можно запускать через gunicorn за nginx.

```bash
gunicorn --bind 127.0.0.1:8001 app
```
