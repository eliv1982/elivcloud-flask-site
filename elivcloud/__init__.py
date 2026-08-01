"""ElivCloud Flask application factory.

Kept intentionally close to the previous single-file app.py: the admin and
/chat routes remain plain app routes (not blueprints) in this slice, per the
approved foundation-slice architecture — only the new bilingual public site
is split into its own blueprint (see elivcloud/blueprints/public.py).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf.csrf import CSRFError
from openai import OpenAI

# Must run before `from config import Config` below: Config reads its
# defaults via os.getenv(...) at class-body-evaluation time (i.e. the moment
# config.py is first imported), so .env has to be loaded into the process
# environment before that import, exactly like the previous single-file
# app.py did at its own module level. Docker/Traefik production is
# unaffected either way — docker-compose.yml injects env vars directly via
# `env_file`, never through a .env file inside the container — but a local
# `python app.py` run outside Docker still relies on this to pick up .env.
load_dotenv()

from chat_backend import (  # noqa: E402
    MAX_MESSAGE_LENGTH,
    build_chat_messages,
    format_rag_context,
    normalize_chat_history,
)
from config import Config  # noqa: E402

from .blueprints.public import public_bp  # noqa: E402
from .content import ContentError, SUPPORTED_LANGUAGES, get_project, load_site_content, localized_url_for  # noqa: E402
from .extensions import csrf, db, login_manager  # noqa: E402
from .forms import EmptyForm, LoginForm  # noqa: E402
from .models import AdminUser, ContactMessage  # noqa: E402

# elivcloud/ is a package one level below the repo root, but templates/,
# static/, and instance/ all still live at the repo root — so Flask's
# root_path must be pointed there explicitly, or it would default to the
# elivcloud/ package directory (Flask(__name__) infers root_path from the
# importing module) and every render_template/static/instance lookup would
# silently miss.
BASE_DIR = Path(__file__).resolve().parent.parent

logger = logging.getLogger("elivcloud")


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


def create_app() -> Flask:
    app = Flask(
        __name__,
        instance_relative_config=True,
        root_path=str(BASE_DIR),
    )
    app.config.from_object(Config)

    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    configure_logging(app)

    app.register_blueprint(public_bp)
    app.jinja_env.globals["localized_url_for"] = localized_url_for

    @app.context_processor
    def inject_globals():
        return {"current_year": datetime.now().year}

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        """Controlled, localized handling for invalid/missing CSRF tokens.

        Flask-WTF's global CSRFProtect (see extensions.py) raises CSRFError
        from a before_request hook that runs after URL matching, so
        request.view_args/request.blueprint are already populated here —
        this only renders the bilingual public error page for requests that
        actually matched a public/<lang> route; every other request
        (admin, legacy redirects, or anything CSRFError-adjacent that
        somehow lacks a resolvable lang) gets a generic, equally safe 400
        with no template dependency, so a broken content file can never
        turn a CSRF rejection into an unhandled second exception. Neither
        branch ever redirects — both return 400 directly, so a rejected
        submission can never look like a success.
        """
        view_args = request.view_args or {}
        lang = view_args.get("lang")

        if request.blueprint == "public" and lang in SUPPORTED_LANGUAGES:
            try:
                site = load_site_content(lang)
                form_copy = site["pages"]["contact"]["form"]
                app.logger.warning("CSRF validation failed on public route %s", request.path)
                return (
                    render_template(
                        "public/error.html",
                        site=site,
                        lang=lang,
                        active_page=None,
                        heading=form_copy["csrf_error_heading"],
                        message=form_copy["csrf_error"],
                    ),
                    400,
                )
            except ContentError as exc:
                app.logger.error(
                    "CSRF error page content load failed for '%s': %s", lang, exc
                )
                # Fall through to the generic branch below.

        app.logger.warning("CSRF validation failed for %s", request.path)
        return "CSRF validation failed. Please go back and try again.", 400

    @login_manager.user_loader
    def load_user(user_id: str):
        admin_username = app.config["ADMIN_USERNAME"]
        if user_id == admin_username:
            return AdminUser(admin_username)
        return None

    # --- Root + legacy redirects ------------------------------------
    # Endpoint names (index/cases/case_detail/contact) are kept identical to
    # the previous single-file app.py on purpose: templates/base.html and
    # the admin templates that extend it still call url_for('index') /
    # url_for('cases') / url_for('contact') and must keep resolving
    # unmodified without editing those templates in this slice.

    @app.route("/")
    def index():
        # Default-language choice is provisional (no Accept-Language
        # negotiation yet), so this is a temporary redirect (302).
        return redirect(url_for("public.home", lang="en"))

    @app.route("/cases")
    def cases():
        # The old URL structure is permanently retired in favor of the
        # bilingual /en|ru/projects routes -> a permanent redirect (301).
        return redirect(url_for("public.projects", lang="en"), code=301)

    @app.route("/cases/<slug>")
    def case_detail(slug: str):
        if get_project("en", slug) is None:
            abort(404)
        return redirect(url_for("public.project_detail", lang="en", slug=slug), code=301)

    @app.route("/contact", methods=["GET", "POST"])
    def contact():
        # Same provisional-default-language reasoning as "/" -> 302.
        return redirect(url_for("public.contact", lang="en"))

    # --- Admin (unchanged behavior; not split into a blueprint this slice) --

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

    # --- Chat / RAG (unchanged behavior) --------------------------------

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
