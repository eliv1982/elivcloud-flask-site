"""Gunicorn-compatible entry point — `gunicorn app:app` must keep working.

All application logic lives in the elivcloud package (see elivcloud/__init__.py
for the create_app() factory).
"""

from elivcloud import create_app

app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
