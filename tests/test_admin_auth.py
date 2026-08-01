"""Admin auth tests — verifies existing (unchanged) admin login/session
behavior still works correctly under the isolated test app, per the
pre-commit review's requirement to separately test (not modify) it.
"""

from __future__ import annotations

import unittest

import tests  # noqa: E402,F401  (sys.path setup — see tests/__init__.py)
from tests.support import create_isolated_app, extract_csrf_token

from config import Config  # noqa: E402


class AdminAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()

    def setUp(self):
        # A fresh client per test so login state never leaks between tests.
        self.client = self.app.test_client()

    def _get_login_csrf_token(self) -> str:
        response = self.client.get("/admin/login")
        return extract_csrf_token(response.data.decode("utf-8"))

    # -- 23: admin login failure remains controlled ------------------------

    def test_admin_login_failure_is_controlled(self):
        token = self._get_login_csrf_token()
        response = self.client.post(
            "/admin/login",
            data={
                "csrf_token": token,
                "username": Config.ADMIN_USERNAME,
                "password": "definitely-not-the-real-password",
            },
        )
        # Re-renders the login form (200), not a redirect into the admin
        # area and not a 500.
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'name="password"', response.data)

        # And the session must genuinely not be authenticated afterward.
        protected = self.client.get("/admin/messages")
        self.assertEqual(protected.status_code, 302)

    # -- 24: admin login success reaches the protected admin area ----------

    def test_admin_login_success_reaches_protected_area(self):
        token = self._get_login_csrf_token()
        response = self.client.post(
            "/admin/login",
            data={
                "csrf_token": token,
                "username": Config.ADMIN_USERNAME,
                "password": Config.ADMIN_PASSWORD,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/admin/messages"))

        protected = self.client.get("/admin/messages")
        self.assertEqual(protected.status_code, 200)

    # -- 25: protected admin route redirects unauthenticated users ---------

    def test_protected_admin_route_redirects_unauthenticated_users(self):
        response = self.client.get("/admin/messages")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login", response.headers["Location"])


if __name__ == "__main__":
    unittest.main()
