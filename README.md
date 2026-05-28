# ElivCloud Flask Portfolio Site

ElivCloud — первая версия личного сайта-портфолио в сфере AI automation, prompt engineering, RAG-ассистентов и AI-ботов.

Проект подготовлен как MVP личного сайта и одновременно закрывает требования учебного задания по личному бренду.

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

Я помогаю бизнесу, экспертам и небольшим командам автоматизировать повторяющиеся бизнес-процессы с помощью AI-ботов, RAG-ассистентов и простых AI-процессов: обработка обращений, отзывов, заявок, документов, клиентских сообщений и баз знаний.

## Кейсы

1. AI-анализ отзывов клиентов
2. Telegram-бот с AI-пояснениями погоды
3. RAG-ассистент по базе знаний и документам
4. Kitchen Helper AI Assistant
5. MoodMuse — AI-генерация открыток

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

## Деплой

Для публичного деплоя Flask-приложение можно запускать через gunicorn за nginx.

```bash
gunicorn --bind 127.0.0.1:8001 app
```
