# ElivCloud

ElivCloud is Elena Shlenskova's evolving, bilingual personal site — a space for her work and projects across law, applied AI, and the connections between them, not a single-purpose portfolio.

## Live site

https://elivcloud.org/

## Current positioning

- ElivCloud is a personal project, not a service offering or a portfolio site for small businesses. Nothing on the site is presented as a service for hire.
- English is the site's primary language; Russian is a full, parallel localization (`/en/...` and `/ru/...`), not a secondary translation layer.
- The site brings together four connected areas: law, corporate and project finance, and international transactions; applied AI and automation; work at the intersection of law, finance, knowledge management and business processes; and conflict resolution, negotiation and complex project delivery.
- Projects are one section of the site (see [Featured projects](#featured-projects)), not the site's identity.
- AI Guide is a navigational assistant that helps visitors find their way around the site — it is not a legal adviser and not a general-purpose personal assistant. See [AI Guide scope](#ai-guide-scope).

## Main sections

Every section is served under a language-prefixed route (`en` or `ru`):

| Section | Route | Purpose |
|---|---|---|
| Home | `/<lang>/` | Introduces ElivCloud, the four connected directions of work, and a set of featured projects. |
| About | `/<lang>/about` | Elena's background across law, finance, conflict/negotiation, technology and project implementation. |
| Expertise | `/<lang>/expertise` | Four areas of work presented as capability pillars (law/finance, social psychology/conflict/negotiation, applied AI/automation, system design/implementation). |
| Projects | `/<lang>/projects` | The full list of selected systems and smaller personal experiments. |
| Experience | `/<lang>/experience` | Experience presented as connected stages, from legal practice to applied AI and full digital systems. |
| Contact | `/<lang>/contact` | A localized contact form (CSRF-protected) for reaching out. |
| AI Guide | `/<lang>/ai-guide` | Describes what an AI-assisted site guide will help with, and its current scope and limits. |

`GET /` redirects to `/en/`.

## Featured projects

Selected systems listed on the Projects page (`content/<lang>/projects.json`):

| Project | Summary | Stack | Repository |
|---|---|---|---|
| AUREL Intake and Analytics Platform (`vibe-order-infra`) | Service intake and request prioritization platform, with secure administration and behavioral analytics. | FastAPI, PostgreSQL, TypeScript, Vite, Docker, Traefik, GitHub Actions | [repo](https://github.com/eliv1982/vibe-order-infra) |
| Business Intake and Triage Assistant (`business-intake-triage-assistant`) | Turns an unstructured business request into a clear processing route, with reasoning kept for audit. | FastAPI, Pydantic, SQLAlchemy, SQLite, OpenAI Structured Outputs, TypeScript | [repo](https://github.com/eliv1982/business-intake-triage-assistant) |
| Mini CRM with Google Reports (`mini-crm-google-reports`) | Compact CRM connecting an API, desktop interface and automated Google Sheets reporting. | FastAPI, SQLite, Tkinter, Google Drive API, Google Sheets API, Docker | [repo](https://github.com/eliv1982/mini-crm-google-reports) |
| Google Sheets Report Automation (`google-sheets-report-automation`) | Automated preparation of management reports in Google Sheets from a desktop interface. | Python, Google Sheets API, Tkinter, OAuth | [repo](https://github.com/eliv1982/google-sheets-report-automation) |
| AI Documentation RAG Agent (`ai-docs-rag-agent`) | Ingests selected documentation into a vector database and answers questions grounded in it via Telegram. | Python, RAG, Pinecone, Telegram, LLM API | [repo](https://github.com/eliv1982/ai-docs-rag-agent) |
| Telegram Bot with Vector Memory (`telegram-vector-memory-bot`) | Telegram assistant with per-user semantic memory and explicit user control over stored data. | Python, aiogram 3, Pinecone, Embeddings, Telegram Bot API | [repo](https://github.com/eliv1982/telegram-vector-memory-bot) |

The Home page features three of these (`vibe-order-infra`, `business-intake-triage-assistant`, `mini-crm-google-reports`); all six appear on the Projects page.

The Projects page also lists three smaller personal experiments (Rise and Shine, MoodMuse, Weather Teller) exploring multimodality and third-party API integration — these have no detail pages, only summaries and repository links.

## Key features

- Bilingual EN/RU site with a language switcher that preserves the current page and falls back to the localized Projects overview if a project slug has no equivalent in the target language.
- Structured, schema-validated JSON content model (see below) — a malformed content file produces a controlled 500, not a broken page.
- Localized contact form (name, email, phone, subject, message) with CSRF protection, per-language validation messages, and submissions stored in SQLite.
- A minimal admin panel (`/admin/login`, `/admin/messages`) to review and manage contact submissions, protected by Flask-Login.
- Automated test suite covering routing, content validation, localization, contact form behavior and admin auth.
- Dockerized deployment behind Traefik with HTTPS in production.

## Architecture / content model

The app is a Flask application factory (`elivcloud/__init__.py:create_app`), imported by `app.py` for Gunicorn compatibility (`gunicorn app:app`). The bilingual public site is a single Flask blueprint (`elivcloud/blueprints/public.py`); admin and the legacy `/chat` endpoint remain plain routes on the app itself.

All public routes are prefixed `/<lang>/` where `lang` is restricted to `en` or `ru` at the routing layer (any other prefix is a normal 404). Page copy is never hardcoded in templates: `elivcloud/content.py` loads and validates `content/<lang>/site.json` and `content/<lang>/projects.json`, then caches the result in memory per language.

Validation is strict and structural, not just "file exists":
- `site.json` must carry every required top-level and per-page key, and each of the seven pages (`home`, `about`, `expertise`, `projects`, `experience`, `contact`, `ai_guide`) is validated against its own required fields.
- List-based content sections have exact expected lengths — 4 Home direction cards, 5 About sections, 4 Expertise pillars, 6 Experience stages, 6 selected projects, 3 personal experiments — so a missing or extra entry fails at load time rather than silently rendering wrong.
- `projects.json` enforces unique project ids/slugs and only allows `http`/`https` repository URLs.

A `ContentError` from a malformed content file is logged and turned into a controlled 500 (or, for the contact form's CSRF-failure page, a safe generic 400) — never a raw exception or a path leaked to the client.

## Tech stack

- **Backend:** Flask, Flask-SQLAlchemy, Flask-WTF (CSRF + forms), Flask-Login (admin auth), Jinja2 templates
- **Database:** SQLite (contact form submissions; admin identity itself comes from environment variables, not the database)
- **Frontend:** server-rendered Jinja templates, plain CSS and vanilla JS (no frontend framework/build step)
- **WSGI/serving:** Gunicorn
- **Containerization:** Docker, Docker Compose
- **Reverse proxy / TLS (production):** Traefik with Let's Encrypt
- **Legacy retrieval backend:** OpenAI API, FAISS (`faiss-cpu`), NumPy — used only by the pre-existing `/chat` endpoint (see [Current status](#current-status--future-development))
- **Tests:** Python's `unittest` (test files are `unittest.TestCase`-based; commonly run via `pytest`)

## Project structure

```text
elivcloud-site/
├── app.py                     # Gunicorn entrypoint: app:app -> create_app()
├── config.py                  # Config (env-driven: SECRET_KEY, DATABASE_URL, admin credentials)
├── elivcloud/
│   ├── __init__.py            # Application factory, admin routes, /chat route, error handlers
│   ├── blueprints/
│   │   └── public.py          # Bilingual public site: home/about/expertise/projects/experience/contact/ai-guide
│   ├── content.py             # content/<lang>/*.json loader + strict validation + caching
│   ├── extensions.py          # Shared db / csrf / login_manager instances
│   ├── forms.py                # ContactForm (localized), LoginForm, EmptyForm
│   └── models.py              # ContactMessage, AdminUser
├── content/
│   ├── en/{site.json, projects.json}
│   └── ru/{site.json, projects.json}
├── templates/
│   ├── public/                # Bilingual site templates (base.html + one per section)
│   ├── admin_login.html       # Admin templates, extend templates/base.html
│   └── admin_messages.html
├── static/
│   ├── css/public.css         # Public bilingual site styles
│   ├── js/public_nav.js       # Public site mobile nav toggle
│   └── brand/source/          # Logo assets (light/dark, horizontal/mark variants)
├── data/                      # RAG knowledge-base source text + generated FAISS index (legacy /chat backend)
├── instance/                  # SQLite database (contact messages)
├── tests/                     # Automated test suite (see Tests)
├── chat_backend.py, rag_index.py, build_index.py   # Legacy /chat RAG pipeline
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

A few files predate the bilingual rebuild and are no longer wired into any route: `templates/base.html` still backs the admin templates above, but `templates/index.html`, `templates/cases.html`, `templates/case_detail.html` and `templates/contact.html` are unused leftovers superseded by `templates/public/`. `static/css/style.css`, `static/css/chat_widget.css`, `static/js/main.js` and `static/js/chat_widget.js` are likewise only referenced by those unused templates, not by `templates/public/base.html`.

## Local setup

Requires Python 3.11+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # then fill in real values
python app.py
```

The app runs at http://127.0.0.1:5000/ and redirects to http://127.0.0.1:5000/en/.

## Environment variables

Defined in `.env.example`:

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Flask session and CSRF signing key. Must be set to a strong, unique value outside local development. |
| `DATABASE_URL` | SQLAlchemy connection string. Defaults to a local SQLite file under `instance/` if unset. |
| `ADMIN_USERNAME` | Username for `/admin/login`. |
| `ADMIN_PASSWORD` | Password for `/admin/login`. Must be overridden outside local development. |
| `OPENAI_API_KEY` | API key used by the legacy `/chat` endpoint's retrieval-augmented backend. |
| `OPENAI_EMBEDDING_MODEL` | Embedding model used when building the FAISS index (`build_index.py`). |
| `OPENAI_CHAT_MODEL` | Chat completion model used by the `/chat` endpoint. |

`.env` is gitignored and must never be committed. Docker Compose injects these directly via `env_file: .env` in production, not by baking them into the image.

## Tests

Test files live under `tests/` and are written as `unittest.TestCase` classes, runnable with either `pytest` or the standard library test runner:

```powershell
pip install pytest   # not declared in requirements.txt
python -m pytest
```

or, without pytest:

```powershell
python -m unittest discover -s tests
```

Coverage includes: routing and redirect/compatibility behavior (`test_app.py`), the `content.py` loader and its schema validation (`test_content.py`), the editorial EN/RU copy itself — required sections rendering correctly in both languages, the six selected projects and three experiments staying in their own lanes (`test_public_content_copy.py`), the bilingual Home page/brand-asset visual foundation and a content-snapshot regression check (`test_visual_foundation.py`), localized contact form validation and isolated-database submission handling (`test_contact_localization.py`), admin login/session behavior (`test_admin_auth.py`), and `/chat` request validation with the OpenAI/FAISS calls mocked out — no live network calls (`test_chat_route.py`).

## Docker

```bash
docker compose build
docker compose up -d
docker compose ps
docker compose logs -f web
docker compose down
```

`docker-compose.yml` builds from the local `Dockerfile`, loads environment variables from `.env`, and mounts `./data` and `./instance` as volumes so both the RAG knowledge base and the SQLite database persist across container rebuilds.

If the legacy `/chat` endpoint's knowledge base needs to be (re)built inside the container:

```bash
docker compose run --rm web python build_index.py
```

## Production deployment overview

The container is built from `Dockerfile` (Python 3.11-slim, Gunicorn with 2 workers) and served on port 5000. In production, `docker-compose.yml` attaches the container to an external Docker network and applies Traefik labels that route `elivcloud.org` and `www.elivcloud.org` to it, terminating HTTPS via Traefik's Let's Encrypt resolver. Environment variables are supplied through `.env` via Compose's `env_file`, never baked into the image.

## Data persistence

Two directories are mounted as volumes so state survives container rebuilds:

- `./instance` — SQLite database (`site.db`) storing contact form submissions viewed through the admin panel.
- `./data` — source text for the legacy `/chat` retrieval backend (`cases.txt`, `company_profile.txt`, `contacts.txt`, `faqs.json`, `process.txt`, `services.txt`) plus the generated FAISS index (`faiss_index.bin`, `faqs_metadata.npy`), which is gitignored and rebuilt via `build_index.py` rather than committed.

## AI Guide scope

The AI Guide page (`/<lang>/ai-guide`) currently describes, in both languages, what an AI-assisted guide to the site will help with: explaining what's on ElivCloud, finding projects related to a topic, showing how the site's areas of work connect, and pointing visitors to the most relevant section. Its stated scope notice is explicit that it draws only on ElivCloud's public materials, that its responses are for orientation and general information, that they do not replace advice from an appropriate professional or constitute a professional recommendation, and that it has no access to private information and cannot make decisions or commitments on Elena's behalf.

As of this rewrite, the page itself is a static description of that scope — it is not yet a connected conversational interface. See below.

## Current status / future development

- The bilingual public site (Home, About, Expertise, Projects, Experience, Contact, AI Guide) is live and content-complete in English and Russian.
- A pre-existing `POST /chat` endpoint (FAISS retrieval + OpenAI completion, backed by `chat_backend.py` and `rag_index.py`) still exists on the app and is covered by tests, but it is not currently exposed through any element of the public site's UI — the AI Guide page is presently a static scope description, not a connected chat interface.
- Planned next step: connect a conversational AI Guide experience to the public site, scoped to navigation and orientation as described on the AI Guide page — not legal advice, not a general personal assistant.
- The old `/cases` and `/cases/<slug>` URLs remain registered as permanent redirects to their English bilingual equivalents (`/en/projects` and `/en/projects/<slug>`), preserving existing inbound links. The legacy `/contact` route and the root `/` currently use temporary redirects to `/en/contact` and `/en/`.
