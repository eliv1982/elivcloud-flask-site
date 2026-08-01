"""Test package init: ensures the repo root is on sys.path so `tests.*`
modules can import the top-level app package and modules (elivcloud, config,
chat_backend, ...) the same way app.py does.

Note: this does NOT set DATABASE_URL. `python -m unittest discover` imports
every package it walks — including elivcloud/, to check for a load_tests
hook — and since 'elivcloud' sorts alphabetically before 'tests', that can
import elivcloud (and therefore config.py) before this file ever runs,
regardless of what a module-level env var override here would say. See
test_app.py's setUpClass for the actual (import-order-proof) fix: it patches
Config.SQLALCHEMY_DATABASE_URI directly, right before calling create_app().
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
