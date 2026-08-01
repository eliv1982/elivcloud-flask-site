"""Unit tests for the elivcloud.content loader — pure module tests, no Flask
application context required."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import tests  # noqa: E402,F401  (sets sys.path before elivcloud import)

from elivcloud import content as content_module  # noqa: E402
from elivcloud.content import (  # noqa: E402
    ContentError,
    SUPPORTED_LANGUAGES,
    load_projects_content,
    load_site_content,
)

REQUIRED_NAV_AND_PAGE_KEYS = (
    "home",
    "about",
    "expertise",
    "projects",
    "experience",
    "contact",
    "ai_guide",
)


def _minimal_page() -> dict:
    return {
        "meta_title": "Title",
        "meta_description": "Description",
        "heading": "Heading",
        "intro": "Intro",
    }


def _minimal_valid_site_dict(lang: str = "en") -> dict:
    """A fully valid site.json structure, for tests to selectively mutate.

    Kept in sync with elivcloud.content's validation rules on purpose: this
    is what "valid" looks like, so negative tests can delete/break exactly
    one thing and still know every *other* check would have passed.
    """
    return {
        "language": lang,
        "provisional": True,
        "provisional_notice": "notice",
        "meta": {"default_title": "title", "default_description": "description"},
        "nav": {key: key for key in REQUIRED_NAV_AND_PAGE_KEYS},
        "pages": {
            "home": _minimal_page(),
            "about": _minimal_page(),
            "expertise": {
                **_minimal_page(),
                "pillars": [{"title": "Pillar", "description": "Pillar description"}],
            },
            "projects": _minimal_page(),
            "experience": _minimal_page(),
            "contact": {
                **_minimal_page(),
                "form": {
                    "name": "Name",
                    "email": "Email",
                    "phone": "Phone",
                    "subject": "Subject",
                    "message": "Message",
                    "submit": "Send",
                    "success": "Sent",
                    "csrf_error_heading": "Error",
                    "csrf_error": "Try again",
                    "validation": {
                        "required": "Required",
                        "invalid_email": "Invalid email",
                        "name_length": "Name too long",
                        "email_length": "Email too long",
                        "phone_length": "Phone too long",
                        "subject_length": "Subject too long",
                        "message_length": "Message too long",
                    },
                },
            },
            "ai_guide": {**_minimal_page(), "scope_notice": "Scope notice"},
        },
    }


def _minimal_valid_projects_dict(lang: str = "en") -> dict:
    return {
        "language": lang,
        "projects": [
            {"id": "project-a", "slug": "project-a", "title": "A", "summary": "Summary A"},
            {"id": "project-b", "slug": "project-b", "title": "B", "summary": "Summary B"},
        ],
    }


class RealContentTests(unittest.TestCase):
    """Exercises the actual content/en and content/ru files shipped in this slice."""

    def setUp(self):
        content_module.clear_content_cache()

    def tearDown(self):
        content_module.clear_content_cache()

    # -- 11: required JSON keys exist ------------------------------------

    def test_site_json_has_required_keys(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                data = load_site_content(lang)
                self.assertIn("language", data)
                self.assertIn("provisional", data)
                self.assertIn("provisional_notice", data)
                self.assertIn("meta", data)
                self.assertIn("nav", data)
                self.assertIn("pages", data)
                for key in REQUIRED_NAV_AND_PAGE_KEYS:
                    self.assertIn(key, data["nav"])
                    self.assertIn(key, data["pages"])

    def test_site_json_page_specific_structures_present(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                data = load_site_content(lang)
                pillars = data["pages"]["expertise"]["pillars"]
                self.assertGreater(len(pillars), 0)
                for pillar in pillars:
                    self.assertIn("title", pillar)
                    self.assertIn("description", pillar)

                form = data["pages"]["contact"]["form"]
                for key in (
                    "name", "email", "phone", "subject", "message", "submit",
                    "success", "csrf_error_heading", "csrf_error",
                ):
                    self.assertIn(key, form)
                for key in (
                    "required", "invalid_email", "name_length", "email_length",
                    "phone_length", "subject_length", "message_length",
                ):
                    self.assertIn(key, form["validation"])

                self.assertIn("scope_notice", data["pages"]["ai_guide"])

    def test_projects_json_has_required_keys(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                data = load_projects_content(lang)
                self.assertIn("projects", data)
                self.assertGreater(len(data["projects"]), 0)
                for project in data["projects"]:
                    for key in ("id", "slug", "title", "summary"):
                        self.assertIn(key, project)
                        self.assertIsInstance(project[key], str)

    # -- 15-16: English and Russian project IDs and slugs match -----------

    def test_en_and_ru_project_ids_match(self):
        en_ids = {p["id"] for p in load_projects_content("en")["projects"]}
        ru_ids = {p["id"] for p in load_projects_content("ru")["projects"]}
        self.assertEqual(en_ids, ru_ids)
        self.assertGreater(len(en_ids), 0)

    def test_en_and_ru_project_slugs_match(self):
        # The shipped content intentionally keeps slugs identical across
        # languages (see content/en|ru/projects.json) so /cases/<slug> can
        # redirect to /en/projects/<slug> and the language switcher can
        # preserve a project-detail URL without a lookup table. If a future
        # change ever needs language-specific slugs, this test should be
        # replaced with an explicit mapping test, not silently deleted.
        en_slugs = {p["slug"] for p in load_projects_content("en")["projects"]}
        ru_slugs = {p["slug"] for p in load_projects_content("ru")["projects"]}
        self.assertEqual(en_slugs, ru_slugs)
        self.assertGreater(len(en_slugs), 0)

    def test_unsupported_language_rejected(self):
        with self.assertRaises(ContentError):
            load_site_content("fr")
        with self.assertRaises(ContentError):
            load_projects_content("fr")


class MalformedSiteContentTests(unittest.TestCase):
    """12: missing/malformed content produces a controlled ContentError,
    not an unhandled exception or a silent fallback."""

    def setUp(self):
        self._original_dir = content_module.CONTENT_DIR
        self._tmp_root = Path(tempfile.mkdtemp())
        content_module.clear_content_cache()

    def tearDown(self):
        content_module.CONTENT_DIR = self._original_dir
        content_module.clear_content_cache()

    def _write_site_json(self, lang: str, data: dict) -> None:
        (self._tmp_root / lang).mkdir(exist_ok=True)
        (self._tmp_root / lang / "site.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        content_module.CONTENT_DIR = self._tmp_root

    def test_missing_file_raises_content_error(self):
        content_module.CONTENT_DIR = self._tmp_root
        with self.assertRaises(ContentError):
            load_site_content("en")

    def test_malformed_json_raises_content_error(self):
        (self._tmp_root / "en").mkdir()
        (self._tmp_root / "en" / "site.json").write_text("{not valid json", encoding="utf-8")
        content_module.CONTENT_DIR = self._tmp_root
        with self.assertRaises(ContentError):
            load_site_content("en")

    def test_incomplete_site_json_raises_content_error(self):
        self._write_site_json("en", {"language": "en"})
        with self.assertRaises(ContentError):
            load_site_content("en")

    def test_content_error_message_has_no_absolute_path(self):
        content_module.CONTENT_DIR = self._tmp_root
        try:
            load_site_content("en")
            self.fail("expected ContentError")
        except ContentError as exc:
            self.assertNotIn(str(self._tmp_root), str(exc))

    # -- 11: language mismatch is rejected ---------------------------------

    def test_language_mismatch_raises_content_error(self):
        # File is physically under content/en/ but internally claims "ru".
        self._write_site_json("en", _minimal_valid_site_dict(lang="ru"))
        with self.assertRaises(ContentError):
            load_site_content("en")

    # -- 12: missing deeply-nested field is rejected -----------------------

    def test_missing_nested_validation_field_raises_content_error(self):
        data = _minimal_valid_site_dict(lang="en")
        del data["pages"]["contact"]["form"]["validation"]["invalid_email"]
        self._write_site_json("en", data)
        with self.assertRaises(ContentError):
            load_site_content("en")

    def test_missing_expertise_pillars_raises_content_error(self):
        data = _minimal_valid_site_dict(lang="en")
        del data["pages"]["expertise"]["pillars"]
        self._write_site_json("en", data)
        with self.assertRaises(ContentError):
            load_site_content("en")

    def test_missing_ai_guide_scope_notice_raises_content_error(self):
        data = _minimal_valid_site_dict(lang="en")
        del data["pages"]["ai_guide"]["scope_notice"]
        self._write_site_json("en", data)
        with self.assertRaises(ContentError):
            load_site_content("en")

    def test_fully_valid_minimal_site_dict_loads_successfully(self):
        # Guards the other tests in this class: if this ever fails, it
        # means _minimal_valid_site_dict() itself is out of sync with the
        # validator, and every "delete one key" test above would be
        # meaningless (it'd fail for the wrong reason).
        self._write_site_json("en", _minimal_valid_site_dict(lang="en"))
        data = load_site_content("en")
        self.assertEqual(data["language"], "en")


class MalformedProjectsContentTests(unittest.TestCase):
    """13-14: duplicate project ids/slugs are rejected rather than
    silently resolving to whichever entry happens to come first."""

    def setUp(self):
        self._original_dir = content_module.CONTENT_DIR
        self._tmp_root = Path(tempfile.mkdtemp())
        content_module.clear_content_cache()

    def tearDown(self):
        content_module.CONTENT_DIR = self._original_dir
        content_module.clear_content_cache()

    def _write_projects_json(self, lang: str, data: dict) -> None:
        (self._tmp_root / lang).mkdir(exist_ok=True)
        (self._tmp_root / lang / "projects.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        content_module.CONTENT_DIR = self._tmp_root

    def test_fully_valid_minimal_projects_dict_loads_successfully(self):
        self._write_projects_json("en", _minimal_valid_projects_dict("en"))
        data = load_projects_content("en")
        self.assertEqual(len(data["projects"]), 2)

    def test_duplicate_project_id_raises_content_error(self):
        data = _minimal_valid_projects_dict("en")
        data["projects"][1]["id"] = data["projects"][0]["id"]
        data["projects"][1]["slug"] = "still-unique-slug"
        self._write_projects_json("en", data)
        with self.assertRaises(ContentError):
            load_projects_content("en")

    def test_duplicate_project_slug_raises_content_error(self):
        data = _minimal_valid_projects_dict("en")
        data["projects"][1]["id"] = "still-unique-id"
        data["projects"][1]["slug"] = data["projects"][0]["slug"]
        self._write_projects_json("en", data)
        with self.assertRaises(ContentError):
            load_projects_content("en")

    def test_projects_language_mismatch_raises_content_error(self):
        self._write_projects_json("en", _minimal_valid_projects_dict(lang="ru"))
        with self.assertRaises(ContentError):
            load_projects_content("en")

    def test_non_string_project_id_raises_content_error(self):
        data = _minimal_valid_projects_dict("en")
        data["projects"][0]["id"] = 123
        self._write_projects_json("en", data)
        with self.assertRaises(ContentError):
            load_projects_content("en")


if __name__ == "__main__":
    unittest.main()
