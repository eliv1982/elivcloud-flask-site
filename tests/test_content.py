"""Unit tests for the elivcloud.content loader — pure module tests, no Flask
application context required."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import tests  # noqa: E402,F401  (sets sys.path before elivcloud import)

from elivcloud import content as content_module  # noqa: E402
from elivcloud.content import (  # noqa: E402
    ContentError,
    SUPPORTED_LANGUAGES,
    get_projects_by_ids,
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
    one thing and still know every *other* check would have passed. List
    lengths here (4 directions, 5 about sections, 4 pillars, 6 stages)
    intentionally match the exact-count rules the loader now enforces.
    """
    return {
        "language": lang,
        "provisional": False,
        "provisional_notice": "",
        "meta": {"default_title": "title", "default_description": "description"},
        "nav": {key: key for key in REQUIRED_NAV_AND_PAGE_KEYS},
        "pages": {
            "home": {
                **_minimal_page(),
                "eyebrow": "Eyebrow",
                "supporting_text": "Supporting text",
                "cta_primary": "Primary CTA",
                "cta_secondary": "Secondary CTA",
                "directions": [
                    {"title": f"Direction {i}", "text": f"Direction text {i}"}
                    for i in range(4)
                ],
                "featured_heading": "Featured heading",
                "featured_intro": "Featured intro",
                "featured_project_ids": ["project-a"],
                "closing_heading": "Closing heading",
                "closing_text": "Closing text",
            },
            "about": {
                **_minimal_page(),
                "sections": [
                    {"title": f"Section {i}", "body": f"Section body {i}"}
                    for i in range(5)
                ],
                "closing": "Closing",
            },
            "expertise": {
                **_minimal_page(),
                "pillars": [
                    {
                        "title": f"Pillar {i}",
                        "description": f"Pillar description {i}",
                        "capabilities": ["Capability"],
                    }
                    for i in range(4)
                ],
                "closing_heading": "Closing heading",
                "closing_text": "Closing text",
            },
            "projects": {
                **_minimal_page(),
                "labels": {
                    "overview": "Overview",
                    "focus": "Focus",
                    "technologies": "Technologies",
                    "view_repository": "View repository",
                    "back_to_projects": "Back to projects",
                },
                "selected_heading": "Selected heading",
                "selected_intro": "Selected intro",
                "experiments_heading": "Experiments heading",
                "experiments_intro": "Experiments intro",
            },
            "experience": {
                **_minimal_page(),
                "stages": [
                    {"title": f"Stage {i}", "text": f"Stage text {i}"}
                    for i in range(6)
                ],
            },
            "contact": {
                **_minimal_page(),
                "supporting_note": "Supporting note",
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
            "ai_guide": {
                **_minimal_page(),
                "scope_heading": "Scope heading",
                "scope_items": ["Scope item"],
                "scope_notice": "Scope notice",
                "status_label": "Status label",
                "placeholder_message": "Placeholder message",
            },
        },
    }


def _minimal_valid_experiment(index: int) -> dict:
    return {
        "id": f"experiment-{index}",
        "title": f"Experiment {index}",
        "summary": f"Summary {index}",
        "focus": f"Focus {index}",
        "topics": ["Topic"],
    }


def _minimal_valid_project(index: int) -> dict:
    label = chr(ord("a") + index)
    return {
        "id": f"project-{label}",
        "slug": f"project-{label}",
        "title": label.upper(),
        "summary": f"Summary {label.upper()}",
        "details": f"Details {label.upper()}",
        "focus": f"Focus {label.upper()}",
        "technologies": ["Python"],
    }


def _minimal_valid_projects_dict(lang: str = "en") -> dict:
    return {
        "language": lang,
        "projects": [_minimal_valid_project(i) for i in range(6)],
        "experiments": [_minimal_valid_experiment(i) for i in range(3)],
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
                self.assertEqual(len(pillars), 4)
                for pillar in pillars:
                    self.assertIn("title", pillar)
                    self.assertIn("description", pillar)
                    self.assertGreater(len(pillar["capabilities"]), 0)

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
                self.assertIn("supporting_note", data["pages"]["contact"])

                self.assertIn("scope_notice", data["pages"]["ai_guide"])
                self.assertGreater(len(data["pages"]["ai_guide"]["scope_items"]), 0)

                projects_page = data["pages"]["projects"]
                for key in (
                    "selected_heading", "selected_intro",
                    "experiments_heading", "experiments_intro",
                ):
                    self.assertIn(key, projects_page)

    def test_site_json_home_about_experience_exact_counts(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                data = load_site_content(lang)
                home = data["pages"]["home"]
                self.assertEqual(len(home["directions"]), 4)
                self.assertEqual(
                    home["featured_project_ids"],
                    [
                        "vibe-order-infra",
                        "business-intake-triage-assistant",
                        "mini-crm-google-reports",
                    ],
                )
                self.assertEqual(len(data["pages"]["about"]["sections"]), 5)
                self.assertEqual(len(data["pages"]["experience"]["stages"]), 6)

    def test_projects_json_has_required_keys(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                data = load_projects_content(lang)
                self.assertIn("projects", data)
                self.assertEqual(len(data["projects"]), 6)
                for project in data["projects"]:
                    for key in ("id", "slug", "title", "summary", "details", "focus"):
                        self.assertIn(key, project)
                        self.assertIsInstance(project[key], str)
                    self.assertGreater(len(project["technologies"]), 0)

                self.assertIn("experiments", data)
                self.assertEqual(len(data["experiments"]), 3)
                for experiment in data["experiments"]:
                    for key in ("id", "title", "summary", "focus"):
                        self.assertIn(key, experiment)
                        self.assertIsInstance(experiment[key], str)
                    self.assertGreater(len(experiment["topics"]), 0)
                    self.assertNotIn("slug", experiment)

    def test_real_en_and_ru_content_loads_with_exactly_six_selected_projects(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                data = load_projects_content(lang)
                self.assertEqual(len(data["projects"]), 6)
                self.assertEqual(len(data["experiments"]), 3)

    # -- get_projects_by_ids -------------------------------------------------

    def test_get_projects_by_ids_returns_matches_in_order(self):
        ids = ["mini-crm-google-reports", "vibe-order-infra"]
        result = get_projects_by_ids("en", ids)
        self.assertEqual([p["id"] for p in result], ids)

    def test_get_projects_by_ids_raises_on_unknown_id(self):
        with self.assertRaises(ContentError):
            get_projects_by_ids("en", ["does-not-exist"])

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

    def test_en_and_ru_experiment_ids_match_in_order(self):
        en_ids = [e["id"] for e in load_projects_content("en")["experiments"]]
        ru_ids = [e["id"] for e in load_projects_content("ru")["experiments"]]
        self.assertEqual(en_ids, ru_ids)
        self.assertEqual(len(en_ids), 3)

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
        self.addCleanup(shutil.rmtree, self._tmp_root, ignore_errors=True)
        self.addCleanup(setattr, content_module, "CONTENT_DIR", self._original_dir)
        self.addCleanup(content_module.clear_content_cache)
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

    def test_missing_ai_guide_scope_items_raises_content_error(self):
        data = _minimal_valid_site_dict(lang="en")
        del data["pages"]["ai_guide"]["scope_items"]
        self._write_site_json("en", data)
        with self.assertRaises(ContentError):
            load_site_content("en")

    def test_missing_home_directions_raises_content_error(self):
        data = _minimal_valid_site_dict(lang="en")
        del data["pages"]["home"]["directions"]
        self._write_site_json("en", data)
        with self.assertRaises(ContentError):
            load_site_content("en")

    def test_home_directions_must_be_exactly_four(self):
        data = _minimal_valid_site_dict(lang="en")
        data["pages"]["home"]["directions"] = data["pages"]["home"]["directions"][:3]
        self._write_site_json("en", data)
        with self.assertRaises(ContentError):
            load_site_content("en")

    def test_missing_home_featured_project_ids_raises_content_error(self):
        data = _minimal_valid_site_dict(lang="en")
        del data["pages"]["home"]["featured_project_ids"]
        self._write_site_json("en", data)
        with self.assertRaises(ContentError):
            load_site_content("en")

    def test_duplicate_home_featured_project_ids_raises_content_error(self):
        data = _minimal_valid_site_dict(lang="en")
        data["pages"]["home"]["featured_project_ids"] = ["project-a", "project-a"]
        self._write_site_json("en", data)
        with self.assertRaises(ContentError):
            load_site_content("en")

    def test_missing_about_sections_raises_content_error(self):
        data = _minimal_valid_site_dict(lang="en")
        del data["pages"]["about"]["sections"]
        self._write_site_json("en", data)
        with self.assertRaises(ContentError):
            load_site_content("en")

    def test_about_sections_must_be_exactly_five(self):
        data = _minimal_valid_site_dict(lang="en")
        data["pages"]["about"]["sections"] = data["pages"]["about"]["sections"][:4]
        self._write_site_json("en", data)
        with self.assertRaises(ContentError):
            load_site_content("en")

    def test_missing_about_closing_raises_content_error(self):
        data = _minimal_valid_site_dict(lang="en")
        del data["pages"]["about"]["closing"]
        self._write_site_json("en", data)
        with self.assertRaises(ContentError):
            load_site_content("en")

    def test_missing_expertise_pillar_capabilities_raises_content_error(self):
        data = _minimal_valid_site_dict(lang="en")
        del data["pages"]["expertise"]["pillars"][0]["capabilities"]
        self._write_site_json("en", data)
        with self.assertRaises(ContentError):
            load_site_content("en")

    def test_expertise_pillars_must_be_exactly_four(self):
        data = _minimal_valid_site_dict(lang="en")
        data["pages"]["expertise"]["pillars"] = data["pages"]["expertise"]["pillars"][:3]
        self._write_site_json("en", data)
        with self.assertRaises(ContentError):
            load_site_content("en")

    def test_missing_experience_stages_raises_content_error(self):
        data = _minimal_valid_site_dict(lang="en")
        del data["pages"]["experience"]["stages"]
        self._write_site_json("en", data)
        with self.assertRaises(ContentError):
            load_site_content("en")

    def test_experience_stages_must_be_exactly_six(self):
        data = _minimal_valid_site_dict(lang="en")
        data["pages"]["experience"]["stages"] = data["pages"]["experience"]["stages"][:5]
        self._write_site_json("en", data)
        with self.assertRaises(ContentError):
            load_site_content("en")

    def test_missing_projects_page_labels_raises_content_error(self):
        data = _minimal_valid_site_dict(lang="en")
        del data["pages"]["projects"]["labels"]
        self._write_site_json("en", data)
        with self.assertRaises(ContentError):
            load_site_content("en")

    def test_missing_projects_page_selected_heading_raises_content_error(self):
        data = _minimal_valid_site_dict(lang="en")
        del data["pages"]["projects"]["selected_heading"]
        self._write_site_json("en", data)
        with self.assertRaises(ContentError):
            load_site_content("en")

    def test_missing_projects_page_experiments_intro_raises_content_error(self):
        data = _minimal_valid_site_dict(lang="en")
        del data["pages"]["projects"]["experiments_intro"]
        self._write_site_json("en", data)
        with self.assertRaises(ContentError):
            load_site_content("en")

    def test_missing_contact_supporting_note_raises_content_error(self):
        data = _minimal_valid_site_dict(lang="en")
        del data["pages"]["contact"]["supporting_note"]
        self._write_site_json("en", data)
        with self.assertRaises(ContentError):
            load_site_content("en")

    def test_provisional_notice_may_be_empty_when_not_provisional(self):
        data = _minimal_valid_site_dict(lang="en")
        data["provisional"] = False
        data["provisional_notice"] = ""
        self._write_site_json("en", data)
        loaded = load_site_content("en")
        self.assertFalse(loaded["provisional"])

    def test_provisional_notice_required_when_provisional_true(self):
        data = _minimal_valid_site_dict(lang="en")
        data["provisional"] = True
        data["provisional_notice"] = ""
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
        self.addCleanup(shutil.rmtree, self._tmp_root, ignore_errors=True)
        self.addCleanup(setattr, content_module, "CONTENT_DIR", self._original_dir)
        self.addCleanup(content_module.clear_content_cache)
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
        self.assertEqual(len(data["projects"]), 6)
        self.assertEqual(len(data["experiments"]), 3)

    def test_five_selected_projects_raises_content_error(self):
        data = _minimal_valid_projects_dict("en")
        data["projects"] = data["projects"][:5]
        self._write_projects_json("en", data)
        with self.assertRaises(ContentError):
            load_projects_content("en")

    def test_seven_selected_projects_raises_content_error(self):
        data = _minimal_valid_projects_dict("en")
        data["projects"].append(_minimal_valid_project(6))
        self._write_projects_json("en", data)
        with self.assertRaises(ContentError):
            load_projects_content("en")

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

    def test_missing_project_technologies_raises_content_error(self):
        data = _minimal_valid_projects_dict("en")
        del data["projects"][0]["technologies"]
        self._write_projects_json("en", data)
        with self.assertRaises(ContentError):
            load_projects_content("en")

    def test_missing_project_details_raises_content_error(self):
        data = _minimal_valid_projects_dict("en")
        del data["projects"][0]["details"]
        self._write_projects_json("en", data)
        with self.assertRaises(ContentError):
            load_projects_content("en")

    def test_missing_project_focus_raises_content_error(self):
        data = _minimal_valid_projects_dict("en")
        del data["projects"][0]["focus"]
        self._write_projects_json("en", data)
        with self.assertRaises(ContentError):
            load_projects_content("en")

    def test_empty_repo_url_raises_content_error(self):
        data = _minimal_valid_projects_dict("en")
        data["projects"][0]["repo_url"] = ""
        self._write_projects_json("en", data)
        with self.assertRaises(ContentError):
            load_projects_content("en")

    def test_project_without_repo_url_loads_successfully(self):
        # repo_url is optional: a project with no known public repository
        # simply omits the button rather than guessing a URL.
        data = _minimal_valid_projects_dict("en")
        self._write_projects_json("en", data)
        loaded = load_projects_content("en")
        self.assertNotIn("repo_url", loaded["projects"][0])

    def test_project_https_repo_url_loads_successfully(self):
        data = _minimal_valid_projects_dict("en")
        data["projects"][0]["repo_url"] = "https://example.com/org/repo"
        self._write_projects_json("en", data)
        loaded = load_projects_content("en")
        self.assertEqual(
            loaded["projects"][0]["repo_url"], "https://example.com/org/repo"
        )

    def test_project_http_repo_url_loads_successfully(self):
        data = _minimal_valid_projects_dict("en")
        data["projects"][0]["repo_url"] = "http://example.com/org/repo"
        self._write_projects_json("en", data)
        loaded = load_projects_content("en")
        self.assertEqual(
            loaded["projects"][0]["repo_url"], "http://example.com/org/repo"
        )

    def test_project_relative_repo_url_raises_content_error(self):
        data = _minimal_valid_projects_dict("en")
        data["projects"][0]["repo_url"] = "/relative/path"
        self._write_projects_json("en", data)
        with self.assertRaises(ContentError) as ctx:
            load_projects_content("en")
        self.assertIn("repo_url", str(ctx.exception))
        self.assertNotIn(str(self._tmp_root), str(ctx.exception))

    def test_project_javascript_repo_url_raises_content_error(self):
        data = _minimal_valid_projects_dict("en")
        data["projects"][0]["repo_url"] = "javascript:alert(1)"
        self._write_projects_json("en", data)
        with self.assertRaises(ContentError) as ctx:
            load_projects_content("en")
        self.assertIn("repo_url", str(ctx.exception))

    def test_project_file_repo_url_raises_content_error(self):
        data = _minimal_valid_projects_dict("en")
        data["projects"][0]["repo_url"] = "file:///etc/passwd"
        self._write_projects_json("en", data)
        with self.assertRaises(ContentError) as ctx:
            load_projects_content("en")
        self.assertIn("repo_url", str(ctx.exception))

    def test_project_https_repo_url_without_host_raises_content_error(self):
        data = _minimal_valid_projects_dict("en")
        data["projects"][0]["repo_url"] = "https://"
        self._write_projects_json("en", data)
        with self.assertRaises(ContentError) as ctx:
            load_projects_content("en")
        self.assertIn("repo_url", str(ctx.exception))

    def test_invalid_project_repo_url_raises_content_error(self):
        data = _minimal_valid_projects_dict("en")
        data["projects"][0]["repo_url"] = "ftp://example.com/repo"
        self._write_projects_json("en", data)
        with self.assertRaises(ContentError) as ctx:
            load_projects_content("en")
        self.assertIn("repo_url", str(ctx.exception))
        self.assertNotIn(str(self._tmp_root), str(ctx.exception))

    # -- experiments ---------------------------------------------------------

    def test_missing_experiments_key_raises_content_error(self):
        data = _minimal_valid_projects_dict("en")
        del data["experiments"]
        self._write_projects_json("en", data)
        with self.assertRaises(ContentError):
            load_projects_content("en")

    def test_experiments_must_be_exactly_three(self):
        data = _minimal_valid_projects_dict("en")
        data["experiments"] = data["experiments"][:2]
        self._write_projects_json("en", data)
        with self.assertRaises(ContentError):
            load_projects_content("en")

    def test_too_many_experiments_raises_content_error(self):
        data = _minimal_valid_projects_dict("en")
        data["experiments"].append(_minimal_valid_experiment(3))
        self._write_projects_json("en", data)
        with self.assertRaises(ContentError):
            load_projects_content("en")

    def test_duplicate_experiment_id_raises_content_error(self):
        data = _minimal_valid_projects_dict("en")
        data["experiments"][1]["id"] = data["experiments"][0]["id"]
        self._write_projects_json("en", data)
        with self.assertRaises(ContentError):
            load_projects_content("en")

    def test_missing_experiment_topics_raises_content_error(self):
        data = _minimal_valid_projects_dict("en")
        del data["experiments"][0]["topics"]
        self._write_projects_json("en", data)
        with self.assertRaises(ContentError):
            load_projects_content("en")

    def test_missing_experiment_focus_raises_content_error(self):
        data = _minimal_valid_projects_dict("en")
        del data["experiments"][0]["focus"]
        self._write_projects_json("en", data)
        with self.assertRaises(ContentError):
            load_projects_content("en")

    def test_experiment_empty_repo_url_raises_content_error(self):
        data = _minimal_valid_projects_dict("en")
        data["experiments"][0]["repo_url"] = ""
        self._write_projects_json("en", data)
        with self.assertRaises(ContentError):
            load_projects_content("en")

    def test_experiment_with_repo_url_loads_successfully(self):
        data = _minimal_valid_projects_dict("en")
        data["experiments"][0]["repo_url"] = "https://github.com/eliv1982/example"
        self._write_projects_json("en", data)
        loaded = load_projects_content("en")
        self.assertEqual(
            loaded["experiments"][0]["repo_url"], "https://github.com/eliv1982/example"
        )

    def test_experiment_http_repo_url_loads_successfully(self):
        data = _minimal_valid_projects_dict("en")
        data["experiments"][0]["repo_url"] = "http://example.com/lab"
        self._write_projects_json("en", data)
        loaded = load_projects_content("en")
        self.assertEqual(
            loaded["experiments"][0]["repo_url"], "http://example.com/lab"
        )

    def test_experiment_without_repo_url_loads_successfully(self):
        data = _minimal_valid_projects_dict("en")
        self._write_projects_json("en", data)
        loaded = load_projects_content("en")
        self.assertNotIn("repo_url", loaded["experiments"][0])

    def test_invalid_experiment_repo_url_raises_content_error(self):
        data = _minimal_valid_projects_dict("en")
        data["experiments"][0]["repo_url"] = "javascript:alert(1)"
        self._write_projects_json("en", data)
        with self.assertRaises(ContentError) as ctx:
            load_projects_content("en")
        self.assertIn("repo_url", str(ctx.exception))
        self.assertNotIn(str(self._tmp_root), str(ctx.exception))

    def test_experiment_relative_repo_url_raises_content_error(self):
        data = _minimal_valid_projects_dict("en")
        data["experiments"][0]["repo_url"] = "../local/repo"
        self._write_projects_json("en", data)
        with self.assertRaises(ContentError) as ctx:
            load_projects_content("en")
        self.assertIn("repo_url", str(ctx.exception))

    def test_experiment_file_repo_url_raises_content_error(self):
        data = _minimal_valid_projects_dict("en")
        data["experiments"][0]["repo_url"] = "file:///tmp/repo"
        self._write_projects_json("en", data)
        with self.assertRaises(ContentError) as ctx:
            load_projects_content("en")
        self.assertIn("repo_url", str(ctx.exception))

    def test_experiment_https_repo_url_without_host_raises_content_error(self):
        data = _minimal_valid_projects_dict("en")
        data["experiments"][0]["repo_url"] = "https://"
        self._write_projects_json("en", data)
        with self.assertRaises(ContentError) as ctx:
            load_projects_content("en")
        self.assertIn("repo_url", str(ctx.exception))

    def test_experiment_without_slug_loads_successfully(self):
        # Experiments deliberately have no slug/detail-route/legacy-redirect
        # shape — only the six selected projects do.
        data = _minimal_valid_projects_dict("en")
        self._write_projects_json("en", data)
        loaded = load_projects_content("en")
        for experiment in loaded["experiments"]:
            self.assertNotIn("slug", experiment)


if __name__ == "__main__":
    unittest.main()
