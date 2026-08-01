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

_REQUIRED_PROJECTS_KEYS = {"language", "projects"}
_REQUIRED_PROJECT_ITEM_KEYS = {"id", "slug", "title", "summary"}


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


# --- site.json --------------------------------------------------------


def _validate_page_common(page: Any, context: str) -> dict[str, Any]:
    page = _require_dict(page, context)
    _require_keys_and_nonempty_strings(page, _COMMON_PAGE_FIELDS, context)
    return page


def _validate_expertise_page(page: dict[str, Any], context: str) -> None:
    pillars = page.get("pillars")
    if not isinstance(pillars, list) or not pillars:
        raise ContentError(f"{context}.pillars must be a non-empty list")
    for index, pillar in enumerate(pillars):
        pillar_context = f"{context}.pillars[{index}]"
        pillar = _require_dict(pillar, pillar_context)
        _require_keys_and_nonempty_strings(pillar, _REQUIRED_PILLAR_KEYS, pillar_context)


def _validate_contact_page(page: dict[str, Any], context: str) -> None:
    form = _require_dict(page.get("form"), f"{context}.form")
    _require_keys_and_nonempty_strings(
        form, _REQUIRED_CONTACT_FORM_KEYS - {"validation"}, f"{context}.form"
    )
    validation = _require_dict(form.get("validation"), f"{context}.form.validation")
    _require_keys_and_nonempty_strings(
        validation, _REQUIRED_CONTACT_VALIDATION_KEYS, f"{context}.form.validation"
    )


def _validate_ai_guide_page(page: dict[str, Any], context: str) -> None:
    _require_nonempty_str(page, "scope_notice", context)


# Page-specific validators beyond the common meta_title/meta_description/
# heading/intro fields every page shares. `home`, `about`, `experience`,
# and `projects` (the site.json page entry, not the projects.json file)
# currently need nothing beyond the common fields — _validate_page_common
# already covers everything those templates index — so they have no entry
# here.
_PAGE_SPECIFIC_VALIDATORS = {
    "expertise": _validate_expertise_page,
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
    _require_nonempty_str(data, "provisional_notice", context)

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


def _validate_projects(data: Any, lang: str) -> dict[str, Any]:
    context = "projects.json"
    data = _require_dict(data, context)
    _require_keys(data, _REQUIRED_PROJECTS_KEYS, context)

    if data.get("language") != lang:
        raise ContentError(
            f"{context} language mismatch: expected {lang!r}, got {data.get('language')!r}"
        )

    projects = data.get("projects")
    if not isinstance(projects, list) or not projects:
        raise ContentError(f"{context}.projects must be a non-empty list")

    seen_ids: set[str] = set()
    seen_slugs: set[str] = set()
    for index, project in enumerate(projects):
        item_context = f"{context}.projects[{index}]"
        project = _require_dict(project, item_context)
        _require_keys_and_nonempty_strings(project, _REQUIRED_PROJECT_ITEM_KEYS, item_context)

        project_id = project["id"]
        if project_id in seen_ids:
            raise ContentError(f"{context} has a duplicate project id: {project_id!r}")
        seen_ids.add(project_id)

        slug = project["slug"]
        if slug in seen_slugs:
            raise ContentError(f"{context} has a duplicate project slug: {slug!r}")
        seen_slugs.add(slug)

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
