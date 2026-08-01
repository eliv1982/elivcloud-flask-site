"""Route/redirect/compatibility tests for the bilingual foundation slice.

Uses stdlib unittest, not pytest: `python -m pytest --version` reported
`No module named pytest` in the active virtualenv at the time this slice was
written, and pytest is not declared in requirements.txt, so per the task's
instructions this suite is written against unittest instead of adding a new
dependency.

No live OpenAI calls are made anywhere in this file: the /chat test only
checks that the route is registered on the URL map, it never invokes the
view. See test_chat_route.py for the mocked /chat behavior tests.
"""

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

import tests  # noqa: E402,F401  (sys.path setup — see tests/__init__.py)
from tests.support import create_isolated_app

from elivcloud.content import get_project  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent

EN_PROJECT_SLUG = get_project("en", "customer-review-mcp")["slug"]
RU_PROJECT_SLUG = get_project("ru", "customer-review-mcp")["slug"]


class ElivCloudRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    # -- 1-3: root redirect + bilingual home pages -----------------------

    def test_root_redirects_to_en(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/en/"))

    def test_en_home_ok(self):
        self.assertEqual(self.client.get("/en/").status_code, 200)

    def test_ru_home_ok(self):
        self.assertEqual(self.client.get("/ru/").status_code, 200)

    # -- 4-5: every required route per language --------------------------

    def test_english_routes(self):
        routes = [
            "/en/",
            "/en/about",
            "/en/expertise",
            "/en/projects",
            f"/en/projects/{EN_PROJECT_SLUG}",
            "/en/experience",
            "/en/contact",
            "/en/ai-guide",
        ]
        for path in routes:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_russian_routes(self):
        routes = [
            "/ru/",
            "/ru/about",
            "/ru/expertise",
            "/ru/projects",
            f"/ru/projects/{RU_PROJECT_SLUG}",
            "/ru/experience",
            "/ru/contact",
            "/ru/ai-guide",
        ]
        for path in routes:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    # -- 6: unsupported language -> 404, not silent fallback --------------

    def test_unsupported_language_returns_404(self):
        for path in ("/fr/", "/fr/about", "/de/projects"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    # -- 7-9: legacy /cases compatibility ---------------------------------

    def test_cases_redirects_permanently_to_en_projects(self):
        response = self.client.get("/cases")
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response.headers["Location"].endswith("/en/projects"))

    def test_case_detail_redirects_to_matching_english_project(self):
        response = self.client.get(f"/cases/{EN_PROJECT_SLUG}")
        self.assertEqual(response.status_code, 301)
        self.assertTrue(
            response.headers["Location"].endswith(f"/en/projects/{EN_PROJECT_SLUG}")
        )

    def test_unknown_project_slug_returns_404(self):
        self.assertEqual(self.client.get("/en/projects/does-not-exist").status_code, 404)
        self.assertEqual(self.client.get("/cases/does-not-exist").status_code, 404)

    def test_legacy_contact_redirects_to_en_contact(self):
        response = self.client.get("/contact")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/en/contact"))

    # -- 13-14: contact form -----------------------------------------------

    def test_contact_get_works_in_both_languages(self):
        for lang in ("en", "ru"):
            with self.subTest(lang=lang):
                self.assertEqual(self.client.get(f"/{lang}/contact").status_code, 200)

    def test_contact_post_without_csrf_token_is_rejected(self):
        response = self.client.post(
            "/en/contact",
            data={
                "name": "Test",
                "email": "test@example.com",
                "subject": "Hello",
                "message": "Hi there",
            },
        )
        # Flask-WTF's global CSRFProtect intercepts before the view runs;
        # elivcloud.handle_csrf_error turns that into a controlled 400 (see
        # test_contact_localization.py for the localized-body assertions).
        self.assertEqual(response.status_code, 400)

    # -- 15-16: admin/chat still reachable ---------------------------------

    def test_admin_login_route_available(self):
        self.assertEqual(self.client.get("/admin/login").status_code, 200)

    def test_chat_route_still_registered(self):
        rules = {rule.rule: rule.methods for rule in self.app.url_map.iter_rules()}
        self.assertIn("/chat", rules)
        self.assertIn("POST", rules["/chat"])

    # -- 17-18: public nav / html lang --------------------------------------

    def test_public_nav_has_no_admin_link(self):
        for lang in ("en", "ru"):
            with self.subTest(lang=lang):
                response = self.client.get(f"/{lang}/")
                self.assertNotIn(b"/admin", response.data)

    def test_html_lang_attribute_matches_route_language(self):
        self.assertIn(b'<html lang="en"', self.client.get("/en/").data)
        self.assertIn(b'<html lang="ru"', self.client.get("/ru/").data)

    # -- 19-20: language switch preserves the current page -----------------

    def test_language_switch_preserves_about_page(self):
        body = self.client.get("/en/about").data.decode("utf-8")
        self.assertIn('href="/ru/about"', body)
        body = self.client.get("/ru/about").data.decode("utf-8")
        self.assertIn('href="/en/about"', body)

    def test_language_switch_preserves_project_detail_slug(self):
        body = self.client.get(f"/en/projects/{EN_PROJECT_SLUG}").data.decode("utf-8")
        self.assertIn(f'href="/ru/projects/{EN_PROJECT_SLUG}"', body)
        body = self.client.get(f"/ru/projects/{RU_PROJECT_SLUG}").data.decode("utf-8")
        self.assertIn(f'href="/en/projects/{RU_PROJECT_SLUG}"', body)

    # -- 21-22: public static assets ----------------------------------------

    def test_public_css_available(self):
        with self.client.get("/static/css/public.css") as response:
            self.assertEqual(response.status_code, 200)

    def test_public_js_available(self):
        with self.client.get("/static/js/public_nav.js") as response:
            self.assertEqual(response.status_code, 200)


class ProjectDetailErrorHandlingTests(unittest.TestCase):
    """17-18 (project-detail specific): a broken projects.json produces a
    controlled 500 for the detail route, exactly like the overview route,
    while an unknown-but-valid slug still 404s normally."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_project_detail_content_error_is_controlled_500(self):
        import shutil
        import tempfile

        import elivcloud.content as content_module

        original_dir = content_module.CONTENT_DIR
        tmp_root = Path(tempfile.mkdtemp())
        try:
            # Copy a real, valid site.json across so this exercises
            # project_detail's *own* handling of a broken projects.json
            # specifically, not the earlier _site_or_500 check that already
            # covers "any ContentError -> controlled 500" for site.json.
            (tmp_root / "en").mkdir()
            shutil.copyfile(
                original_dir / "en" / "site.json", tmp_root / "en" / "site.json"
            )
            # No projects.json written at all -> ContentError: file not found.
            content_module.CONTENT_DIR = tmp_root
            content_module.clear_content_cache()

            response = self.client.get(f"/en/projects/{EN_PROJECT_SLUG}")
            self.assertEqual(response.status_code, 500)
            self.assertNotIn(str(tmp_root).encode(), response.data)
        finally:
            content_module.CONTENT_DIR = original_dir
            content_module.clear_content_cache()
            shutil.rmtree(tmp_root, ignore_errors=True)

    def test_unknown_slug_still_404s_when_content_loads_correctly(self):
        response = self.client.get("/en/projects/does-not-exist-either")
        self.assertEqual(response.status_code, 404)


class DeploymentFilesUnchangedTests(unittest.TestCase):
    """Guardrail: this slice must not touch Docker/Traefik configuration.

    Temporary slice guardrail, not a permanent architectural fixture: it
    exists to prove this and the preceding foundation-slice task never
    touched deployment files, and can be retired once that's no longer in
    question.
    """

    # Hashes captured from the working tree before this slice's changes.
    EXPECTED_SHA256 = {
        "Dockerfile": "88f287f92065c109332bc1421010a311170eecbbbc0495bcf483447208854976",
        "docker-compose.yml": "6085eb03fddb4039d87954cd1f4fbe4b69cab65387baaa9099f053769716aa3e",
    }

    def test_dockerfile_and_compose_unchanged(self):
        for filename, expected_hash in self.EXPECTED_SHA256.items():
            with self.subTest(filename=filename):
                path = REPO_ROOT / filename
                actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertEqual(actual_hash, expected_hash, f"{filename} was modified")


if __name__ == "__main__":
    unittest.main()
