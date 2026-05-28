import logging
import os
from datetime import datetime

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
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
        "slug": "review-analysis",
        "title": "AI-анализ отзывов клиентов",
        "summary": "Помощник анализирует отзывы, выделяет частые темы, тональность, срочные обращения и помогает подготовить черновики ответов клиентам.",
        "task": "У бизнеса есть отзывы из разных источников. Их сложно читать вручную, негатив может теряться, а ответы занимают много времени.",
        "solution": "AI-помощник принимает текст отзыва, определяет тему, тональность, важные детали и предлагает черновик ответа.",
        "result": "Команда быстрее видит повторяющиеся проблемы, спокойнее отвечает клиентам и получает краткую картину по качеству сервиса.",
        "approaches": [
            "Prompt engineering",
            "Structured output",
            "Text classification",
            "AI-assisted response drafting",
        ],
    },
    {
        "slug": "weather-teller",
        "title": "Telegram-бот с AI-пояснениями погоды",
        "summary": "Telegram-бот помогает получать прогноз, сравнивать локации и источники данных, а также показывает краткие AI-пояснения простым языком.",
        "task": "Пользователю нужно быстро понимать прогноз без перегруза цифрами и сложными формулировками.",
        "solution": "Собран Telegram-бот с погодными сценариями, сохранёнными локациями, сравнением прогнозов и AI-текстами.",
        "result": "Пользователь получает понятный прогноз и может сравнивать данные без ручного поиска в разных сервисах.",
        "approaches": [
            "Telegram bot",
            "API integration",
            "PostgreSQL",
            "Docker",
            "AI wording",
            "Weather data processing",
        ],
    },
    {
        "slug": "rag-assistant",
        "title": "RAG-ассистент по базе знаний и документам",
        "summary": "Ассистент помогает искать ответы в документах и базе знаний, сохраняя связь ответа с источниками.",
        "task": "В документах много информации, но вручную искать нужные фрагменты долго и неудобно.",
        "solution": "Проектируется RAG-подход: загрузка материалов, поиск релевантных фрагментов, генерация ответа с опорой на найденный контекст.",
        "result": "Пользователь быстрее получает ответ по материалам и видит, на какие источники он опирается.",
        "approaches": [
            "RAG",
            "Embeddings",
            "Vector search",
            "Source-aware answers",
            "Insufficient-basis mode",
        ],
    },
    {
        "slug": "kitchen-helper",
        "title": "Kitchen Helper AI Assistant",
        "summary": "AI-помощник помогает составить простой план ужина из продуктов, которые уже есть дома.",
        "task": "Пользователю нужно быстро получить понятный и практичный план без сложных рецептов и лишних покупок.",
        "solution": "Подготовлены управляемые промпты, JSON-формат ответа и проверка структуры результата.",
        "result": "Получается стабильный структурированный ответ, который можно использовать как основу функции Telegram-бота.",
        "approaches": [
            "Prompt iteration",
            "JSON output",
            "Validation",
            "Python script",
            "Telegram bot foundation",
        ],
    },
    {
        "slug": "moodmuse",
        "title": "MoodMuse — AI-генерация открыток",
        "summary": "Telegram-бот помогает создать персонализированную открытку: повод, стиль, текст, изображение и настройки профиля.",
        "task": "Пользователю нужно быстро получить красивый текст и визуальную идею открытки без долгого ручного подбора формулировок.",
        "solution": "Собран сценарий генерации с профилем пользователя, выбором стиля, подтверждением данных и AI-генерацией текста и изображения.",
        "result": "Пользователь получает готовую карточку/открытку и может быстро изменить текст, изображение или язык подписи.",
        "approaches": [
            "Telegram bot",
            "OpenAI-compatible text generation",
            "Image generation",
            "Profile settings",
            "UX flow",
        ],
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

    with app.app_context():
        db.create_all()
        app.logger.info("Database initialized in %s", app.config["SQLALCHEMY_DATABASE_URI"])

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
