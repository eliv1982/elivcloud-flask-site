"""Public, bilingual blueprint: Home / About / Expertise / Projects /
Experience / Contact / AI Guide.

Every route is prefixed with a language segment restricted to exactly
{"en", "ru"} via Werkzeug's built-in `any` converter — a request for any
other language prefix (e.g. /fr/about) simply matches no rule and falls
through to Flask's normal 404 handling, with no silent fallback.
"""

from __future__ import annotations

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    url_for,
)

from ..content import ContentError, get_project, load_projects_content, load_site_content
from ..extensions import db
from ..forms import ContactForm
from ..models import ContactMessage

public_bp = Blueprint("public", __name__)


@public_bp.url_value_preprocessor
def _pull_lang(endpoint, values):
    """Stash the current language on `g` so `_push_lang` can default it
    into `url_for()` calls that omit `lang` explicitly."""
    if values is not None:
        g.lang = values.get("lang")


@public_bp.url_defaults
def _push_lang(endpoint, values):
    if "lang" in values:
        return
    lang = getattr(g, "lang", None)
    if lang and current_app.url_map.is_endpoint_expecting(endpoint, "lang"):
        values["lang"] = lang


def _site_or_500(lang: str):
    try:
        return load_site_content(lang)
    except ContentError as exc:
        current_app.logger.error("Site content load failed for '%s': %s", lang, exc)
        abort(500)


def _projects_or_500(lang: str):
    try:
        return load_projects_content(lang)
    except ContentError as exc:
        current_app.logger.error("Projects content load failed for '%s': %s", lang, exc)
        abort(500)


@public_bp.route("/<any(en, ru):lang>/")
def home(lang):
    site = _site_or_500(lang)
    return render_template(
        "public/home.html",
        site=site,
        lang=lang,
        page=site["pages"]["home"],
        active_page="home",
    )


@public_bp.route("/<any(en, ru):lang>/about")
def about(lang):
    site = _site_or_500(lang)
    return render_template(
        "public/about.html",
        site=site,
        lang=lang,
        page=site["pages"]["about"],
        active_page="about",
    )


@public_bp.route("/<any(en, ru):lang>/expertise")
def expertise(lang):
    site = _site_or_500(lang)
    return render_template(
        "public/expertise.html",
        site=site,
        lang=lang,
        page=site["pages"]["expertise"],
        active_page="expertise",
    )


@public_bp.route("/<any(en, ru):lang>/projects")
def projects(lang):
    site = _site_or_500(lang)
    projects_data = _projects_or_500(lang)
    return render_template(
        "public/projects.html",
        site=site,
        lang=lang,
        page=site["pages"]["projects"],
        projects=projects_data["projects"],
        active_page="projects",
    )


@public_bp.route("/<any(en, ru):lang>/projects/<slug>")
def project_detail(lang, slug):
    site = _site_or_500(lang)
    # _projects_or_500 handles a malformed/missing projects.json the same
    # way the overview route does (logged, controlled 500, no path leak).
    # get_project() below only re-reads the now-cached data to look up the
    # slug, so it can no longer raise ContentError at this point — it can
    # only return None, which is the normal "unknown slug" 404 path, never
    # converted into a 500.
    _projects_or_500(lang)
    project = get_project(lang, slug)
    if project is None:
        abort(404)
    return render_template(
        "public/project_detail.html",
        site=site,
        lang=lang,
        project=project,
        active_page="projects",
    )


@public_bp.route("/<any(en, ru):lang>/experience")
def experience(lang):
    site = _site_or_500(lang)
    return render_template(
        "public/experience.html",
        site=site,
        lang=lang,
        page=site["pages"]["experience"],
        active_page="experience",
    )


@public_bp.route("/<any(en, ru):lang>/contact", methods=["GET", "POST"])
def contact(lang):
    """Single handler serves both /en/contact and /ru/contact so the
    CSRF/validation/storage logic is never duplicated per language — only
    the label text and flash message pulled from site.json differ."""
    site = _site_or_500(lang)
    page = site["pages"]["contact"]
    form = ContactForm(lang=lang)

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
        current_app.logger.info(
            "Contact form submitted by %s <%s>", message.name, message.email
        )
        flash(page["form"]["success"], "success")
        return redirect(url_for("public.contact", lang=lang))

    return render_template(
        "public/contact.html",
        site=site,
        lang=lang,
        page=page,
        form=form,
        active_page="contact",
    )


@public_bp.route("/<any(en, ru):lang>/ai-guide")
def ai_guide(lang):
    site = _site_or_500(lang)
    return render_template(
        "public/ai_guide.html",
        site=site,
        lang=lang,
        page=site["pages"]["ai_guide"],
        active_page="ai_guide",
    )
