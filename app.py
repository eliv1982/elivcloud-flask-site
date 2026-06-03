import logging
import os
from datetime import datetime

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from openai import OpenAI
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm, CSRFProtect
from dotenv import load_dotenv
from wtforms import PasswordField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length

from config import Config
from chat_backend import (
    MAX_MESSAGE_LENGTH,
    build_chat_messages,
    format_rag_context,
    normalize_chat_history,
)


load_dotenv()


db = SQLAlchemy()
csrf = CSRFProtect()
login_manager = LoginManager()
login_manager.login_view = "admin_login"
login_manager.login_message = "Войдите в админ-панель, чтобы продолжить."
login_manager.login_message_category = "warning"


logger = logging.getLogger("elivcloud")


CASES_DATA = [
    {
        "slug": "customer-review-mcp",
        "title": "Customer Review MCP Assistant",
        "summary": "AI-ассистент для мониторинга отзывов клиентов: помогает находить негатив, смотреть статистику, добавлять новые отзывы и готовить черновики ответов через MCP-style архитектуру.",
        "task": "У малого бизнеса отзывы и клиентские сообщения могут накапливаться в разных местах. Негатив легко пропустить, а подготовка спокойных ответов занимает время.",
        "solution": "Собран Telegram-ассистент с отдельным MCP-style FastAPI server, SQLite-хранилищем, LLM-router и набором инструментов: поиск отзывов, негативные отзывы, статистика, добавление отзыва, черновик ответа и калькулятор.",
        "result": "Бизнес быстрее видит проблемные отзывы, не теряет срочные обращения и получает основу для спокойной коммуникации с клиентами. Потенциальный эффект — меньше ручного просмотра отзывов и быстрее реакция на негатив.",
        "approaches": [
            "MCP-style architecture",
            "Telegram bot",
            "FastAPI",
            "SQLite analytics",
            "LLM tool routing",
            "JSON Schema tools",
            "AI reply drafts",
        ],
        "repo_url": "https://github.com/eliv1982/customer-review-mcp-assistant",
    },
    {
        "slug": "legal-rag-assistant",
        "title": "Legal RAG Assistant — независимые гарантии",
        "summary": "RAG-ассистент по независимым гарантиям: помогает искать ответы в юридических материалах и формировать source-aware ответы с опорой на документы.",
        "task": "Юридические материалы объёмные, а быстрый поиск по нормам, практике и условиям гарантий требует времени и аккуратности.",
        "solution": "Собран web MVP и CLI RAG-ассистента: поиск по базе документов, генерация ответа с опорой на найденный контекст, логирование взаимодействий и базовые метрики.",
        "result": "Пользователь быстрее получает предварительный ответ по материалам и видит, на какие источники он опирается. Потенциальный эффект — меньше времени на первичный поиск и структурирование информации.",
        "approaches": [
            "RAG",
            "ChromaDB",
            "OpenAI API",
            "FastAPI",
            "SQLite logging",
            "Source-aware answers",
            "Docker deployment",
        ],
        "repo_url": "https://github.com/eliv1982/rag-assistant-independent-guarantees",
    },
    {
        "slug": "ai-agent-toolbox",
        "title": "AI Agent Toolbox",
        "summary": "Локальный AI-агент с набором инструментов: поиск, погода, валюты, криптовалюты, QR-коды, работа с файлами, память, напоминания, калькулятор и анализ текста.",
        "task": "Пользователю нужен единый помощник, который может не только отвечать текстом, но и вызывать конкретные инструменты под задачу.",
        "solution": "Собран учебно-портфолио проект на OpenAI/LangChain с CLI и Streamlit web-интерфейсом, 11 инструментами, памятью, логами и preview/download артефактов.",
        "result": "Проект показывает, как AI-ассистент может работать как практический toolbox, а не просто чат. Потенциальный эффект — объединение нескольких мелких рабочих сценариев в одном интерфейсе.",
        "approaches": [
            "LangChain",
            "OpenAI-compatible LLM",
            "Streamlit",
            "Tool calling",
            "Local memory",
            "Logs",
            "Artifacts",
        ],
        "repo_url": "https://github.com/eliv1982/ai-agent-toolbox-homework",
    },
    {
        "slug": "weather-teller",
        "title": "Weather Teller — Telegram-бот с AI-пояснениями погоды",
        "summary": "Telegram-бот для прогноза погоды, сохранённых локаций, подписок, сравнения прогнозов и кратких AI-пояснений простым языком.",
        "task": "Пользователю нужно быстро понимать прогноз без перегруза цифрами, сложными формулировками и ручного сравнения разных локаций.",
        "solution": "Собран Telegram-бот с погодными сценариями, OpenWeather API, PostgreSQL, Docker, сохранёнными локациями, подписками, сравнением и AI-текстами.",
        "result": "Пользователь получает понятный прогноз, может сохранять локации и получать регулярные уведомления. Потенциальный эффект — меньше ручного поиска и больше практической пользы от погодных данных.",
        "approaches": [
            "Telegram bot",
            "OpenWeather API",
            "PostgreSQL",
            "Docker",
            "API integration",
            "AI wording",
            "Notifications",
        ],
        "repo_url": "https://github.com/eliv1982/weather_teller_bot",
    },
    {
        "slug": "moodmuse",
        "title": "MoodMuse — персонализированные AI-открытки",
        "summary": "Telegram-бот для создания персонализированных открыток: повод, стиль, текст, изображение, голосовой ввод и настройки профиля.",
        "task": "Пользователю нужно быстро создать красивую и уместную открытку без долгого подбора формулировок и визуальной идеи.",
        "solution": "Собран сценарий генерации с профилем пользователя, выбором стиля, подтверждением данных, AI-генерацией текста и изображения, а также возможностью менять текст, картинку или язык подписи.",
        "result": "Пользователь получает готовую карточку/открытку и может быстро адаптировать результат. Потенциальный эффект — меньше времени на создание персонального поздравления и меньше шаблонных текстов.",
        "approaches": [
            "Telegram bot",
            "AI text generation",
            "Image generation",
            "Voice input",
            "Profile settings",
            "UX flow",
        ],
        "repo_url": "https://github.com/eliv1982/moodmuse-bot",
    },
    {
        "slug": "open-model-tone-finetuning",
        "title": "Open Model Tone Fine-tuning",
        "summary": "LoRA fine-tuning открытой русскоязычной модели под спокойный tone of voice для бизнес-коммуникации, клиентского сервиса и AI-автоматизации.",
        "task": "Малому бизнесу и командам поддержки важно отвечать клиентам в едином стиле: спокойно, понятно, без давления, жаргона и случайных формулировок.",
        "solution": "Подготовлен собственный датасет из 100 пар instruction/output на русском языке, реализовано обучение LoRA-адаптера поверх открытой модели и демонстрационный inference для сравнения baseline и версии с LoRA.",
        "result": "Кейс показывает полный цикл адаптации стиля модели: от датасета до проверки результата. Потенциальный эффект — более единый tone of voice в клиентских ответах и меньше ручной правки типовых сообщений.",
        "approaches": [
            "LoRA fine-tuning",
            "Hugging Face Transformers",
            "PEFT",
            "PyTorch",
            "Russian dataset",
            "Baseline vs LoRA comparison",
            "Tone of voice",
        ],
        "repo_url": "https://github.com/eliv1982/open-model-tone-finetuning",
    },
]


class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(32), nullable=True)
    subject = db.Column(db.String(180), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class AdminUser(UserMixin):
    def __init__(self, username: str):
        self.id = username


class ContactForm(FlaskForm):
    name = StringField("Имя", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    phone = StringField("Телефон", validators=[Length(max=32)])
    subject = StringField("Тема", validators=[DataRequired(), Length(max=180)])
    message = TextAreaField("Сообщение", validators=[DataRequired(), Length(max=5000)])
    submit = SubmitField("Отправить заявку")


class LoginForm(FlaskForm):
    username = StringField("Логин", validators=[DataRequired(), Length(max=80)])
    password = PasswordField("Пароль", validators=[DataRequired(), Length(max=255)])
    submit = SubmitField("Войти")


class EmptyForm(FlaskForm):
    submit = SubmitField("Подтвердить")


def configure_logging(app: Flask) -> None:
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    app.logger.handlers = logger.handlers
    app.logger.setLevel(logger.level)


def get_case_by_slug(slug: str):
    return next((case for case in CASES_DATA if case["slug"] == slug), None)


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    configure_logging(app)

    @app.context_processor
    def inject_globals():
        return {"current_year": datetime.now().year}

    @login_manager.user_loader
    def load_user(user_id: str):
        admin_username = app.config["ADMIN_USERNAME"]
        if user_id == admin_username:
            return AdminUser(admin_username)
        return None

    @app.route("/")
    def index():
        return render_template("index.html", cases=CASES_DATA)

    @app.route("/cases")
    def cases():
        return render_template("cases.html", cases=CASES_DATA)

    @app.route("/cases/<slug>")
    def case_detail(slug: str):
        case = get_case_by_slug(slug)
        if case is None:
            abort(404)
        return render_template("case_detail.html", case=case)

    @app.route("/contact", methods=["GET", "POST"])
    def contact():
        form = ContactForm()
        if form.validate_on_submit():
            message = ContactMessage(
                name=form.name.data.strip(),
                email=form.email.data.strip(),
                phone=(form.phone.data or "").strip(),
                subject=form.subject.data.strip(),
                message=form.message.data.strip(),
            )
            db.session.add(message)
            db.session.commit()
            app.logger.info(
                "Contact form submitted by %s <%s>", message.name, message.email
            )
            flash("Спасибо! Сообщение отправлено. Я свяжусь с вами в ближайшее время.", "success")
            return redirect(url_for("contact"))
        return render_template("contact.html", form=form)

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if current_user.is_authenticated:
            return redirect(url_for("admin_messages"))

        form = LoginForm()
        if form.validate_on_submit():
            username_ok = form.username.data == app.config["ADMIN_USERNAME"]
            password_ok = form.password.data == app.config["ADMIN_PASSWORD"]
            if username_ok and password_ok:
                login_user(AdminUser(app.config["ADMIN_USERNAME"]))
                app.logger.info("Admin logged in from %s", request.remote_addr)
                flash("Вы вошли в админ-панель.", "success")
                return redirect(url_for("admin_messages"))
            flash("Неверный логин или пароль.", "danger")
        return render_template("admin_login.html", form=form)

    @app.route("/admin/messages")
    @login_required
    def admin_messages():
        messages = ContactMessage.query.order_by(ContactMessage.created_at.desc()).all()
        read_form = EmptyForm()
        delete_form = EmptyForm()
        return render_template(
            "admin_messages.html",
            messages=messages,
            read_form=read_form,
            delete_form=delete_form,
        )

    @app.route("/admin/messages/<int:message_id>/read", methods=["POST"])
    @login_required
    def admin_mark_read(message_id: int):
        form = EmptyForm()
        if form.validate_on_submit():
            message = ContactMessage.query.get_or_404(message_id)
            message.is_read = True
            db.session.commit()
            app.logger.info("Message %s marked as read by admin", message_id)
            flash("Заявка отмечена как прочитанная.", "success")
        else:
            flash("Ошибка CSRF. Повторите действие.", "danger")
        return redirect(url_for("admin_messages"))

    @app.route("/admin/messages/<int:message_id>/delete", methods=["POST"])
    @login_required
    def admin_delete_message(message_id: int):
        form = EmptyForm()
        if form.validate_on_submit():
            message = ContactMessage.query.get_or_404(message_id)
            db.session.delete(message)
            db.session.commit()
            app.logger.info("Message %s deleted by admin", message_id)
            flash("Заявка удалена.", "info")
        else:
            flash("Ошибка CSRF. Повторите действие.", "danger")
        return redirect(url_for("admin_messages"))

    @app.route("/admin/logout")
    @login_required
    def admin_logout():
        logout_user()
        flash("Вы вышли из админ-панели.", "info")
        return redirect(url_for("admin_login"))

    @app.route("/chat", methods=["POST"])
    @csrf.exempt
    def chat():
        if not request.is_json:
            return jsonify({"error": "Ожидается JSON-запрос."}), 400

        data = request.get_json(silent=True) or {}
        user_message = data.get("message", "")

        if not isinstance(user_message, str) or not user_message.strip():
            return jsonify({"error": "Поле 'message' обязательно и должно быть непустой строкой."}), 400

        user_message = user_message.strip()
        if len(user_message) > MAX_MESSAGE_LENGTH:
            return jsonify(
                {"error": f"Сообщение слишком длинное. Максимум {MAX_MESSAGE_LENGTH} символов."}
            ), 400

        history = normalize_chat_history(data.get("history", []))

        try:
            from rag_index import search_knowledge_base
            rag_results = search_knowledge_base(user_message, top_k=4)
        except FileNotFoundError as exc:
            app.logger.error("RAG index missing: %s", exc)
            return jsonify(
                {"error": "Индекс базы знаний не найден. Запустите: python build_index.py"}
            ), 500
        except RuntimeError as exc:
            app.logger.error("RAG runtime error: %s", exc)
            return jsonify({"error": "Ошибка конфигурации RAG. Проверьте OPENAI_API_KEY."}), 500

        rag_context = format_rag_context(rag_results)
        messages = build_chat_messages(user_message, rag_context, history)

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            return jsonify({"error": "OPENAI_API_KEY не задан."}), 500

        chat_model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

        try:
            client = OpenAI(api_key=api_key)
            completion = client.chat.completions.create(
                model=chat_model,
                messages=messages,
                temperature=0.2,
            )
            answer = completion.choices[0].message.content.strip()
        except Exception as exc:
            app.logger.error("OpenAI chat error: %s", type(exc).__name__)
            return jsonify({"error": "Ошибка при обращении к AI-сервису. Попробуйте позже."}), 500

        sources = [
            {
                "score": round(r["score"], 4),
                "source": r["source"],
                "kind": r["kind"],
                "question": r["question"],
            }
            for r in rag_results
        ]

        return jsonify({"answer": answer, "sources": sources})

    with app.app_context():
        db.create_all()
        app.logger.info("Database initialized in %s", app.config["SQLALCHEMY_DATABASE_URI"])

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
