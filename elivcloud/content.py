"""Structured bilingual content loader for ElivCloud.

Content lives under content/<lang>/{site,projects}.json — deliberately
outside the Docker-mounted data/ directory, which holds the FAISS knowledge
base for the /chat assistant, not page copy. This module is intentionally
small (standard-library JSON + a handful of reusable set/type checks) rather
than a validation framework, matching the size of this site. It has no Flask
import-time dependency other than for `localized_url_for`, so
load_site_content/load_projects_content/get_project can be unit tested
without an application context, and the same functions can later back the
AI Guide's own content lookups.

Validation is deliberately strict about the exact fields templates and
routes index directly (see _validate_site/_validate_projects below): once a
file passes validation, callers are expected to index it directly
(`site["pages"]["contact"]["form"]["validation"]["required"]`, etc.) rather
than defending every access with `.get(..., default)` — the validation step
is what makes that safe.
"""

from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import urlparse

from flask import request, url_for
from werkzeug.routing import BuildError

SUPPORTED_LANGUAGES = {"en", "ru"}

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"

_REQUIRED_SITE_KEYS = {
    "language",
    "provisional",
    "provisional_notice",
    "meta",
    "nav",
    "pages",
}
_REQUIRED_META_KEYS = {"default_title", "default_description"}
_REQUIRED_NAV_KEYS = {
    "home",
    "about",
    "expertise",
    "projects",
    "experience",
    "contact",
    "ai_guide",
}
_REQUIRED_PAGE_KEYS = _REQUIRED_NAV_KEYS

# Fields every page dict must carry — matches what templates/public/*.html
# actually reference on `page` (meta_title/meta_description in <head>,
# heading/intro in the body) for every one of the seven page sections.
_COMMON_PAGE_FIELDS = {"meta_title", "meta_description", "heading", "intro"}

_REQUIRED_PILLAR_KEYS = {"title", "description"}

# Shared shapes for the small list-of-{title,text}-dicts sections that
# recur across pages (home direction cards, about body sections,
# experience stages) — each entry needs exactly a title plus one prose key.
_REQUIRED_TITLE_TEXT_KEYS = {"title", "text"}
_REQUIRED_TITLE_BODY_KEYS = {"title", "body"}

_REQUIRED_HOME_PAGE_STRING_KEYS = {
    "eyebrow",
    "supporting_text",
    "cta_primary",
    "cta_secondary",
    "featured_heading",
    "featured_intro",
    "closing_heading",
    "closing_text",
}
_REQUIRED_EXPERTISE_CLOSING_KEYS = {"closing_heading", "closing_text"}
_REQUIRED_PROJECTS_PAGE_LABEL_KEYS = {
    "overview",
    "focus",
    "technologies",
    "view_repository",
    "back_to_projects",
}
# The Projects page renders two clearly separate sections — completed
# selected systems, and smaller personal experiments — each with its own
# heading/intro copy pulled from content rather than hardcoded in the
# template.
_REQUIRED_PROJECTS_PAGE_SECTION_KEYS = {
    "selected_heading",
    "selected_intro",
    "experiments_heading",
    "experiments_intro",
}
_REQUIRED_AI_GUIDE_STRING_KEYS = {
    "scope_heading",
    "scope_notice",
    "status_label",
    "placeholder_message",
}

# Exact counts for the recurring list sections — these are content-model
# decisions (four direction cards, five About sections, four Expertise
# pillars, six Experience stages, six selected projects, three Personal
# experiments), not just "must be non-empty", so the loader enforces them
# rather than leaving drift to be caught only by a test.
_HOME_DIRECTIONS_COUNT = 4
_ABOUT_SECTIONS_COUNT = 5
_EXPERTISE_PILLARS_COUNT = 4
_EXPERIENCE_STAGES_COUNT = 6
_SELECTED_PROJECTS_COUNT = 6
_EXPERIMENTS_COUNT = 3

_REQUIRED_CONTACT_VALIDATION_KEYS = {
    "required",
    "invalid_email",
    "name_length",
    "email_length",
    "phone_length",
    "subject_length",
    "message_length",
}
_REQUIRED_CONTACT_FORM_KEYS = {
    "name",
    "email",
    "phone",
    "subject",
    "message",
    "submit",
    "success",
    "csrf_error_heading",
    "csrf_error",
    "validation",
}

_REQUIRED_PROJECTS_KEYS = {"language", "projects", "experiments"}
_REQUIRED_PROJECT_ITEM_KEYS = {"id", "slug", "title", "summary", "details", "focus"}

# Personal experiments are smaller, no detail-page/slug/legacy-redirect
# entries — id/title/summary/focus plus a short topics list, distinct from
# the fuller selected-project shape above.
_REQUIRED_EXPERIMENT_ITEM_KEYS = {"id", "title", "summary", "focus"}


class ContentError(Exception):
    """Raised when site content is missing, unreadable, or malformed.

    Messages reference only file names and dotted logical keys (e.g.
    "site.json pages.contact.form.validation"), never absolute filesystem
    paths, so they stay safe to surface in logs or, indirectly, in a
    generic 500 response.
    """


_cache: dict[tuple[str, str], dict[str, Any]] = {}
_cache_lock = Lock()


def _require_supported_language(lang: str) -> None:
    if lang not in SUPPORTED_LANGUAGES:
        raise ContentError(f"Unsupported language: {lang!r}")


def _read_json(path: Path) -> Any:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ContentError(f"Content file not found: {path.name}") from None
    except OSError as exc:
        raise ContentError(f"Content file could not be read: {path.name}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ContentError(f"Content file is not valid JSON: {path.name}") from exc


# --- small reusable validation helpers (stdlib only, no schema framework) --


def _require_dict(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContentError(f"{context} must be a JSON object")
    return value


def _require_keys(data: dict[str, Any], required: set[str], context: str) -> None:
    missing = required - data.keys()
    if missing:
        raise ContentError(f"{context} is missing keys: {sorted(missing)}")


def _require_nonempty_str(data: dict[str, Any], key: str, context: str) -> None:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ContentError(f"{context}.{key} must be a non-empty string")


def _require_keys_and_nonempty_strings(
    data: dict[str, Any], required: set[str], context: str
) -> None:
    """Common case: a dict whose required keys must all be present *and*
    hold non-empty string values (labels, messages, headings, ...)."""
    _require_keys(data, required, context)
    for key in required:
        _require_nonempty_str(data, key, context)


def _require_nonempty_str_list(value: Any, context: str) -> list[str]:
    """List fields holding short copy items (capability bullets, AI Guide
    scope items, project technology tags, featured-project id references)."""
    if not isinstance(value, list) or not value:
        raise ContentError(f"{context} must be a non-empty list")
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ContentError(f"{context}[{index}] must be a non-empty string")
    return value


def _require_list_of_dicts_with_keys(
    items: Any, required_keys: set[str], context: str, *, count: int | None = None
) -> None:
    """Recurring shape: a list of dicts that each carry `required_keys` as
    non-empty strings (direction cards, about sections, experience stages).

    `count`, when given, is an exact-length requirement (e.g. "exactly four
    direction cards") rather than just "non-empty" — these list lengths are
    content-model decisions, not incidental, so drift should fail loudly at
    load time instead of only being caught by a test.
    """
    if not isinstance(items, list) or not items:
        raise ContentError(f"{context} must be a non-empty list")
    if count is not None and len(items) != count:
        raise ContentError(f"{context} must contain exactly {count} item(s)")
    for index, item in enumerate(items):
        item_context = f"{context}[{index}]"
        item = _require_dict(item, item_context)
        _require_keys_and_nonempty_strings(item, required_keys, item_context)


# --- site.json --------------------------------------------------------


def _validate_page_common(page: Any, context: str) -> dict[str, Any]:
    page = _require_dict(page, context)
    _require_keys_and_nonempty_strings(page, _COMMON_PAGE_FIELDS, context)
    return page


def _validate_home_page(page: dict[str, Any], context: str) -> None:
    _require_keys_and_nonempty_strings(page, _REQUIRED_HOME_PAGE_STRING_KEYS, context)
    _require_list_of_dicts_with_keys(
        page.get("directions"),
        _REQUIRED_TITLE_TEXT_KEYS,
        f"{context}.directions",
        count=_HOME_DIRECTIONS_COUNT,
    )
    featured_ids = _require_nonempty_str_list(
        page.get("featured_project_ids"), f"{context}.featured_project_ids"
    )
    if len(set(featured_ids)) != len(featured_ids):
        raise ContentError(f"{context}.featured_project_ids has duplicate entries")


def _validate_about_page(page: dict[str, Any], context: str) -> None:
    _require_nonempty_str(page, "closing", context)
    _require_list_of_dicts_with_keys(
        page.get("sections"),
        _REQUIRED_TITLE_BODY_KEYS,
        f"{context}.sections",
        count=_ABOUT_SECTIONS_COUNT,
    )


def _validate_expertise_page(page: dict[str, Any], context: str) -> None:
    _require_keys_and_nonempty_strings(page, _REQUIRED_EXPERTISE_CLOSING_KEYS, context)
    pillars = page.get("pillars")
    if not isinstance(pillars, list) or len(pillars) != _EXPERTISE_PILLARS_COUNT:
        raise ContentError(
            f"{context}.pillars must contain exactly {_EXPERTISE_PILLARS_COUNT} item(s)"
        )
    for index, pillar in enumerate(pillars):
        pillar_context = f"{context}.pillars[{index}]"
        pillar = _require_dict(pillar, pillar_context)
        _require_keys_and_nonempty_strings(pillar, _REQUIRED_PILLAR_KEYS, pillar_context)
        _require_nonempty_str_list(
            pillar.get("capabilities"), f"{pillar_context}.capabilities"
        )


def _validate_experience_page(page: dict[str, Any], context: str) -> None:
    _require_list_of_dicts_with_keys(
        page.get("stages"),
        _REQUIRED_TITLE_TEXT_KEYS,
        f"{context}.stages",
        count=_EXPERIENCE_STAGES_COUNT,
    )


def _validate_projects_page(page: dict[str, Any], context: str) -> None:
    labels = _require_dict(page.get("labels"), f"{context}.labels")
    _require_keys_and_nonempty_strings(
        labels, _REQUIRED_PROJECTS_PAGE_LABEL_KEYS, f"{context}.labels"
    )
    _require_keys_and_nonempty_strings(
        page, _REQUIRED_PROJECTS_PAGE_SECTION_KEYS, context
    )


def _validate_contact_page(page: dict[str, Any], context: str) -> None:
    _require_nonempty_str(page, "supporting_note", context)
    form = _require_dict(page.get("form"), f"{context}.form")
    _require_keys_and_nonempty_strings(
        form, _REQUIRED_CONTACT_FORM_KEYS - {"validation"}, f"{context}.form"
    )
    validation = _require_dict(form.get("validation"), f"{context}.form.validation")
    _require_keys_and_nonempty_strings(
        validation, _REQUIRED_CONTACT_VALIDATION_KEYS, f"{context}.form.validation"
    )


def _validate_ai_guide_page(page: dict[str, Any], context: str) -> None:
    _require_keys_and_nonempty_strings(page, _REQUIRED_AI_GUIDE_STRING_KEYS, context)
    _require_nonempty_str_list(page.get("scope_items"), f"{context}.scope_items")


# Page-specific validators beyond the common meta_title/meta_description/
# heading/intro fields every page shares.
_PAGE_SPECIFIC_VALIDATORS = {
    "home": _validate_home_page,
    "about": _validate_about_page,
    "expertise": _validate_expertise_page,
    "experience": _validate_experience_page,
    "projects": _validate_projects_page,
    "contact": _validate_contact_page,
    "ai_guide": _validate_ai_guide_page,
}


def _validate_site(data: Any, lang: str) -> dict[str, Any]:
    context = "site.json"
    data = _require_dict(data, context)
    _require_keys(data, _REQUIRED_SITE_KEYS, context)

    if data.get("language") != lang:
        raise ContentError(
            f"{context} language mismatch: expected {lang!r}, got {data.get('language')!r}"
        )

    if not isinstance(data.get("provisional"), bool):
        raise ContentError(f"{context}.provisional must be a boolean")
    provisional_notice = data.get("provisional_notice")
    if not isinstance(provisional_notice, str):
        raise ContentError(f"{context}.provisional_notice must be a string")
    # Only required to carry actual text while provisional is true — the
    # notice is never rendered once a page ships as final, so an empty
    # string is the correct steady-state value rather than stale copy.
    if data["provisional"] and not provisional_notice.strip():
        raise ContentError(
            f"{context}.provisional_notice must be a non-empty string when provisional is true"
        )

    meta = _require_dict(data.get("meta"), f"{context}.meta")
    _require_keys_and_nonempty_strings(meta, _REQUIRED_META_KEYS, f"{context}.meta")

    nav = _require_dict(data.get("nav"), f"{context}.nav")
    _require_keys_and_nonempty_strings(nav, _REQUIRED_NAV_KEYS, f"{context}.nav")

    pages = _require_dict(data.get("pages"), f"{context}.pages")
    _require_keys(pages, _REQUIRED_PAGE_KEYS, f"{context}.pages")

    for page_key in _REQUIRED_PAGE_KEYS:
        page_context = f"{context}.pages.{page_key}"
        page = _validate_page_common(pages[page_key], page_context)
        specific_validator = _PAGE_SPECIFIC_VALIDATORS.get(page_key)
        if specific_validator is not None:
            specific_validator(page, page_context)

    return data


# --- projects.json -----------------------------------------------------


def _validate_repo_url(value: Any, context: str) -> None:
    """Accept optional absolute http(s) URLs with a non-empty host.

    Missing/None stays allowed (repo_url is optional). When present, only
    non-empty http/https URLs with a network location are accepted —
    relative paths and schemes such as javascript:/data:/file:/ftp: are
    rejected so templates never render an unsafe href from content.
    """
    if value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise ContentError(f"{context} must be a non-empty string when present")

    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ContentError(
            f"{context} must be an absolute http or https URL with a host"
        )


def _validate_experiments(experiments: Any, context: str) -> None:
    if not isinstance(experiments, list) or len(experiments) != _EXPERIMENTS_COUNT:
        raise ContentError(
            f"{context} must contain exactly {_EXPERIMENTS_COUNT} item(s)"
        )

    seen_ids: set[str] = set()
    for index, experiment in enumerate(experiments):
        item_context = f"{context}[{index}]"
        experiment = _require_dict(experiment, item_context)
        _require_keys_and_nonempty_strings(
            experiment, _REQUIRED_EXPERIMENT_ITEM_KEYS, item_context
        )
        _require_nonempty_str_list(experiment.get("topics"), f"{item_context}.topics")
        _validate_repo_url(experiment.get("repo_url"), f"{item_context}.repo_url")

        experiment_id = experiment["id"]
        if experiment_id in seen_ids:
            raise ContentError(f"{context} has a duplicate experiment id: {experiment_id!r}")
        seen_ids.add(experiment_id)


def _validate_projects(data: Any, lang: str) -> dict[str, Any]:
    context = "projects.json"
    data = _require_dict(data, context)
    _require_keys(data, _REQUIRED_PROJECTS_KEYS, context)

    if data.get("language") != lang:
        raise ContentError(
            f"{context} language mismatch: expected {lang!r}, got {data.get('language')!r}"
        )

    projects = data.get("projects")
    if (
        not isinstance(projects, list)
        or len(projects) != _SELECTED_PROJECTS_COUNT
    ):
        raise ContentError(
            f"{context}.projects must contain exactly "
            f"{_SELECTED_PROJECTS_COUNT} item(s)"
        )

    seen_ids: set[str] = set()
    seen_slugs: set[str] = set()
    for index, project in enumerate(projects):
        item_context = f"{context}.projects[{index}]"
        project = _require_dict(project, item_context)
        _require_keys_and_nonempty_strings(project, _REQUIRED_PROJECT_ITEM_KEYS, item_context)
        _require_nonempty_str_list(
            project.get("technologies"), f"{item_context}.technologies"
        )
        _validate_repo_url(project.get("repo_url"), f"{item_context}.repo_url")

        project_id = project["id"]
        if project_id in seen_ids:
            raise ContentError(f"{context} has a duplicate project id: {project_id!r}")
        seen_ids.add(project_id)

        slug = project["slug"]
        if slug in seen_slugs:
            raise ContentError(f"{context} has a duplicate project slug: {slug!r}")
        seen_slugs.add(slug)

    _validate_experiments(data.get("experiments"), f"{context}.experiments")

    return data


def load_site_content(lang: str) -> dict[str, Any]:
    """Return the cached, validated site.json content for lang."""
    _require_supported_language(lang)
    cache_key = ("site", lang)

    with _cache_lock:
        cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    data = _validate_site(_read_json(CONTENT_DIR / lang / "site.json"), lang)

    with _cache_lock:
        _cache[cache_key] = data
    return data


def load_projects_content(lang: str) -> dict[str, Any]:
    """Return the cached, validated projects.json content for lang."""
    _require_supported_language(lang)
    cache_key = ("projects", lang)

    with _cache_lock:
        cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    data = _validate_projects(_read_json(CONTENT_DIR / lang / "projects.json"), lang)

    with _cache_lock:
        _cache[cache_key] = data
    return data


def get_project(lang: str, slug: str) -> dict[str, Any] | None:
    """Return the project dict matching slug in lang, or None if absent.

    Uniqueness of slugs within a language is already enforced by
    _validate_projects at load time, so there is exactly zero or one match
    here — never a silent "first of several" pick.
    """
    data = load_projects_content(lang)
    for project in data["projects"]:
        if project["slug"] == slug:
            return project
    return None


def get_projects_by_ids(lang: str, ids: list[str]) -> list[dict[str, Any]]:
    """Return the project dicts matching ids, in the given order.

    Backs the Home page's featured-projects section. site.json's
    home.featured_project_ids and projects.json are two independently
    validated files, so nothing at load time guarantees every id in one
    still exists in the other — this raises ContentError on a mismatch
    (routed to a controlled 500, same as any other content problem) rather
    than letting a stale id surface as a bare KeyError from the template.
    """
    data = load_projects_content(lang)
    by_id = {project["id"]: project for project in data["projects"]}
    missing = [project_id for project_id in ids if project_id not in by_id]
    if missing:
        raise ContentError(f"projects.json is missing referenced id(s): {missing}")
    return [by_id[project_id] for project_id in ids]


def get_contact_validation_messages(lang: str) -> dict[str, str]:
    """Return the localized ContactForm validator messages for lang.

    Safe to index directly (no .get(..., default)): load_site_content's
    validation guarantees pages.contact.form.validation carries every key
    in _REQUIRED_CONTACT_VALIDATION_KEYS.
    """
    site = load_site_content(lang)
    return site["pages"]["contact"]["form"]["validation"]


def clear_content_cache() -> None:
    """Test helper: drop all cached content so the next load re-reads disk."""
    with _cache_lock:
        _cache.clear()


def localized_url_for(target_lang: str, endpoint: str | None = None, **overrides: Any) -> str:
    """Build a URL for target_lang, preserving the current endpoint/args.

    Backs the language switcher (and is exposed as a Jinja global to every
    template) so pages never manually concatenate '/en/' or '/ru/' onto a
    path. If the current view is a project detail page and the slug has no
    equivalent entry in target_lang, falls back to that language's Projects
    overview instead of producing a broken link.
    """
    if target_lang not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported language: {target_lang!r}")

    endpoint = endpoint or request.endpoint or "public.home"
    values = dict(request.view_args or {})
    values.pop("lang", None)
    values.update(overrides)
    values["lang"] = target_lang

    if endpoint == "public.project_detail":
        slug = values.get("slug")
        if slug is not None and get_project(target_lang, slug) is None:
            return url_for("public.projects", lang=target_lang)

    try:
        return url_for(endpoint, **values)
    except BuildError:
        return url_for("public.home", lang=target_lang)
