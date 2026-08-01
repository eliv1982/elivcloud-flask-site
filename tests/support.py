"""Shared helpers for building isolated Flask app instances in tests, and
for driving CSRF-protected forms through the real test client.

Every test module that needs a running app calls create_isolated_app(),
never create_app() directly, so the real dev instance/site.db is never at
risk of being touched by the test suite.
"""

from __future__ import annotations

import re

import tests  # noqa: F401  (sys.path setup — see tests/__init__.py)

from config import Config
from elivcloud import create_app

TEST_DATABASE_URI = "sqlite:///:memory:"

_CSRF_INPUT_RE = re.compile(r'<input[^>]*name="csrf_token"[^>]*>')
_VALUE_ATTR_RE = re.compile(r'value="([^"]*)"')


def create_isolated_app():
    """Build a fresh Flask app bound to an isolated in-memory database.

    Patches Config.SQLALCHEMY_DATABASE_URI directly, immediately before
    calling create_app() (which runs db.create_all() as its last step),
    rather than relying on a DATABASE_URL environment variable set from
    test module import: `python -m unittest discover` imports every package
    it walks — including elivcloud/, to check for a load_tests hook — and
    since 'elivcloud' sorts alphabetically before 'tests', that can import
    elivcloud (and therefore config.py, which reads DATABASE_URL once at
    import time) before any test module's own env-var override would ever
    run. Mutating the class attribute here, right before create_app(), is
    not subject to that import-order race.

    The assertion below is a hard stop, not a soft check: if the isolated
    URI somehow didn't take, this raises immediately rather than silently
    letting a test proceed against the real instance/site.db.
    """
    Config.SQLALCHEMY_DATABASE_URI = TEST_DATABASE_URI
    app = create_app()
    app.config.update(TESTING=True)
    assert app.config["SQLALCHEMY_DATABASE_URI"] == TEST_DATABASE_URI, (
        "Test app is not bound to the isolated in-memory database — refusing "
        "to continue rather than risk touching the real instance/site.db"
    )
    return app


def extract_csrf_token(html: str) -> str:
    """Pull the csrf_token hidden input's value out of rendered form HTML.

    Used by tests that need a *real*, session-bound CSRF token (rather than
    omitting one, which is what the existing CSRF-rejection tests do): GET
    the form first with the same test client, extract the token from that
    response, then POST it back on the same client so the session cookie
    matches.
    """
    tag_match = _CSRF_INPUT_RE.search(html)
    if not tag_match:
        raise AssertionError("csrf_token input not found in rendered form HTML")
    value_match = _VALUE_ATTR_RE.search(tag_match.group(0))
    if not value_match:
        raise AssertionError("csrf_token input has no value attribute")
    return value_match.group(1)
