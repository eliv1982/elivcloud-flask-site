"""Tests for the localized Contact form (Fix 1), localized CSRF failure
handling (Fix 2), and the isolated-database proof for successful
submissions (Fixes required by the pre-commit review).

All apps in this file come from tests.support.create_isolated_app(), which
patches Config.SQLALCHEMY_DATABASE_URI to an in-memory SQLite before
create_app() ever runs db.create_all() — see that module's docstring for
why an environment-variable-based approach is not reliable under
`unittest discover`. No test in this file opens instance/site.db.
"""

from __future__ import annotations

import unittest

import tests  # noqa: E402,F401  (sys.path setup — see tests/__init__.py)
from tests.support import create_isolated_app, extract_csrf_token

from elivcloud.content import load_site_content  # noqa: E402
from elivcloud.models import ContactMessage  # noqa: E402


def _get_csrf_token(client, path: str) -> str:
    response = client.get(path)
    return extract_csrf_token(response.data.decode("utf-8"))


def _invalid_form_payload(csrf_token: str) -> dict:
    """Blank required fields + a malformed email, valid CSRF token."""
    return {
        "csrf_token": csrf_token,
        "name": "",
        "email": "not-an-email",
        "phone": "",
        "subject": "",
        "message": "",
    }


def _valid_form_payload(csrf_token: str, suffix: str = "") -> dict:
    return {
        "csrf_token": csrf_token,
        "name": f"Test User{suffix}",
        "email": "test-user@example.com",
        "phone": "",
        "subject": "Hello",
        "message": "This is a valid test message.",
    }


class LocalizedValidationMessageTests(unittest.TestCase):
    """1-4: required-field and invalid-email messages are localized per
    language, never the WTForms English defaults leaking onto /ru/contact."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def _submit_invalid_form(self, lang: str) -> bytes:
        token = _get_csrf_token(self.client, f"/{lang}/contact")
        response = self.client.post(
            f"/{lang}/contact", data=_invalid_form_payload(token)
        )
        self.assertEqual(response.status_code, 200)  # re-renders the form with errors
        return response.data

    def test_english_required_field_message(self):
        messages = load_site_content("en")["pages"]["contact"]["form"]["validation"]
        body = self._submit_invalid_form("en").decode("utf-8")
        self.assertIn(messages["required"], body)

    def test_russian_required_field_message(self):
        messages = load_site_content("ru")["pages"]["contact"]["form"]["validation"]
        body = self._submit_invalid_form("ru").decode("utf-8")
        self.assertIn(messages["required"], body)
        # The English default WTForms message must never leak onto the
        # Russian page.
        self.assertNotIn("This field is required.", body)

    def test_english_invalid_email_message(self):
        messages = load_site_content("en")["pages"]["contact"]["form"]["validation"]
        body = self._submit_invalid_form("en").decode("utf-8")
        self.assertIn(messages["invalid_email"], body)

    def test_russian_invalid_email_message(self):
        messages = load_site_content("ru")["pages"]["contact"]["form"]["validation"]
        body = self._submit_invalid_form("ru").decode("utf-8")
        self.assertIn(messages["invalid_email"], body)
        self.assertNotIn("Invalid email address", body)

    def test_name_email_message_length_validators_are_localized(self):
        # Exercise the Length validators specifically (not just DataRequired
        # and Email), on both languages, with an over-long name/email.
        for lang in ("en", "ru"):
            with self.subTest(lang=lang):
                messages = load_site_content(lang)["pages"]["contact"]["form"]["validation"]
                token = _get_csrf_token(self.client, f"/{lang}/contact")
                payload = _valid_form_payload(token)
                payload["name"] = "x" * 121
                payload["email"] = ("y" * 250) + "@example.com"  # > 255 chars total
                payload["message"] = "z" * 5001
                response = self.client.post(f"/{lang}/contact", data=payload)
                body = response.data.decode("utf-8")
                self.assertEqual(response.status_code, 200)
                self.assertIn(messages["name_length"], body)
                self.assertIn(messages["email_length"], body)
                self.assertIn(messages["message_length"], body)


class LocalizedCsrfFailureTests(unittest.TestCase):
    """5-6: a missing/invalid CSRF token on the public contact routes
    returns a controlled, localized 400 — never a 500, never a redirect
    that would look like a successful submission."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_english_csrf_failure_response(self):
        messages = load_site_content("en")["pages"]["contact"]["form"]
        response = self.client.post(
            "/en/contact",
            data={
                "name": "Test",
                "email": "test@example.com",
                "subject": "Hello",
                "message": "Hi there",
            },
        )
        self.assertEqual(response.status_code, 400)
        body = response.data.decode("utf-8")
        self.assertIn(messages["csrf_error_heading"], body)
        self.assertIn(messages["csrf_error"], body)
        self.assertIn('<html lang="en"', body)

    def test_russian_csrf_failure_response(self):
        messages = load_site_content("ru")["pages"]["contact"]["form"]
        response = self.client.post(
            "/ru/contact",
            data={
                "name": "Тест",
                "email": "test@example.com",
                "subject": "Привет",
                "message": "Сообщение",
            },
        )
        self.assertEqual(response.status_code, 400)
        body = response.data.decode("utf-8")
        self.assertIn(messages["csrf_error_heading"], body)
        self.assertIn(messages["csrf_error"], body)
        self.assertIn('<html lang="ru"', body)

    def test_csrf_failure_response_has_no_internal_details(self):
        response = self.client.post("/en/contact", data={"name": "x"})
        body = response.data.decode("utf-8")
        self.assertNotIn(str(self.app.root_path), body)
        self.assertNotIn("Traceback", body)
        self.assertNotIn("CSRFError", body)

    def test_csrf_failure_never_redirects(self):
        response = self.client.post("/en/contact", data={"name": "x"})
        self.assertNotIn(response.status_code, (301, 302, 303, 307, 308))


class SuccessfulContactSubmissionTests(unittest.TestCase):
    """7-10: a real CSRF token round-tripped through the same client lets a
    valid submission through in both languages, persists exactly one row,
    and proves the isolated in-memory database (not instance/site.db) is
    what received it."""

    def setUp(self):
        # Fresh app + fresh in-memory DB per test method (not per class):
        # these tests assert exact row *counts*, so they must not
        # accumulate rows across test methods sharing one app.
        self.app = create_isolated_app()
        self.client = self.app.test_client()

    def test_successful_english_contact_post(self):
        token = _get_csrf_token(self.client, "/en/contact")
        response = self.client.post(
            "/en/contact", data=_valid_form_payload(token, suffix="-en")
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/en/contact"))

        with self.app.app_context():
            self.assertEqual(ContactMessage.query.count(), 1)
            saved = ContactMessage.query.one()
            self.assertEqual(saved.name, "Test User-en")

    def test_successful_russian_contact_post(self):
        token = _get_csrf_token(self.client, "/ru/contact")
        response = self.client.post(
            "/ru/contact", data=_valid_form_payload(token, suffix="-ru")
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/ru/contact"))

        with self.app.app_context():
            self.assertEqual(ContactMessage.query.count(), 1)
            saved = ContactMessage.query.one()
            self.assertEqual(saved.name, "Test User-ru")

    def test_successful_submission_persists_exactly_one_row(self):
        token = _get_csrf_token(self.client, "/en/contact")
        self.client.post("/en/contact", data=_valid_form_payload(token, suffix="-once"))

        with self.app.app_context():
            self.assertEqual(ContactMessage.query.count(), 1)

    def test_database_is_isolated_in_memory_not_the_real_dev_database(self):
        # Structural proof, not a peek into the real file: instance/site.db
        # is never opened by this test at all, only the app's own
        # configured URI is inspected.
        self.assertEqual(
            self.app.config["SQLALCHEMY_DATABASE_URI"], "sqlite:///:memory:"
        )
        self.assertNotIn("instance", self.app.config["SQLALCHEMY_DATABASE_URI"])


if __name__ == "__main__":
    unittest.main()
