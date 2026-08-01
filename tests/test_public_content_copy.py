"""Coverage for the ElivCloud editorial content revision.

Exercises the approved EN/RU content itself (not just the loader's generic
schema rules, which test_content.py already covers): that every content
file is no longer marked provisional, that the provisional notice never
renders, that each page's required sections render in both languages, that
the six selected projects and three personal experiments render correctly
and stay in their own separate lanes (experiments have no detail pages),
that the editorial repositioning (ElivCloud as Elena's broader personal
project — law, conflict/negotiation, applied AI, implementation, curiosity —
rather than a CV-equivalent of Elena herself) actually landed in the copy,
and that no retired/forbidden language crept back in.

Every comparison against a rendered response body goes through _rendered(),
which applies the same MarkupSafe escaping Jinja's autoescape applies to any
`{{ value }}` interpolation (e.g. "Elena's" -> "Elena&#39;s") — several of
the approved strings contain apostrophes, so a raw substring check would
fail against the escaped HTML even though the content renders correctly.

Uses tests.support.create_isolated_app() like every other route-level test
module in this suite, so nothing here touches the real instance/site.db.
No live OpenAI call is made anywhere in this file.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from markupsafe import escape

import tests  # noqa: E402,F401  (sys.path setup — see tests/__init__.py)
from tests.support import create_isolated_app

from elivcloud.content import (  # noqa: E402
    SUPPORTED_LANGUAGES,
    load_projects_content,
    load_site_content,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_TEMPLATES_DIR = REPO_ROOT / "templates" / "public"

APPROVED_PROJECT_IDS = {
    "vibe-order-infra",
    "business-intake-triage-assistant",
    "mini-crm-google-reports",
    "google-sheets-report-automation",
    "ai-docs-rag-agent",
    "telegram-vector-memory-bot",
}
HOME_FEATURED_PROJECT_IDS = [
    "vibe-order-infra",
    "business-intake-triage-assistant",
    "mini-crm-google-reports",
]
APPROVED_EXPERIMENT_IDS = ["rise-and-shine", "moodmuse", "weather-teller"]

# Ids from the retired freelance/bot-service *project* catalogue — must
# never reappear among the six selected projects. Note "moodmuse" and
# "weather-teller" are deliberately reused as Personal Experiment ids in
# this revision, so this check is scoped to the "projects" array only.
OLD_PROJECT_IDS = {
    "customer-review-mcp",
    "legal-rag-assistant",
    "ai-agent-toolbox",
    "weather-teller",
    "moodmuse",
    "open-model-tone-finetuning",
}
# Titles from that same retired catalogue that must never reappear as a
# *selected project* title. Scoped to the "projects" array only (not the
# whole file) because "MoodMuse" and "Weather Teller" are approved,
# reintroduced Personal Experiment titles in this revision.
OLD_PROJECT_TITLES = (
    "Customer Review MCP Assistant",
    "Legal RAG Assistant",
    "AI Agent Toolbox",
    "Open Model Tone Fine-tuning",
)

# Sales/availability language the boundaries explicitly forbid for this
# personal, non-freelance site.
FREELANCE_SALES_PHRASES = (
    "hire me",
    "order a service",
    "book a call",
    "available for hire",
    "заказать услугу",
    "нанять меня",
    "свободна для проектов",
)

# Claims of clinical/professional psychological services this personal site
# must never make (Elena's psychology interest is framed as knowledge/
# curiosity, not a service offering).
THERAPY_OR_COUNSELLING_PHRASES = (
    "therapy",
    "psychotherapy",
    "counselling",
    "counseling",
    "терапия",
    "психотерапия",
    "психологическая помощь",
    "психологическое консультирование",
)

# Legal-only / attorney-client framing this revision explicitly removes
# from AI Guide in favour of a general "not advice on any matter" notice.
LEGAL_ONLY_AI_GUIDE_PHRASES = (
    "attorney-client",
    "legal advice",
    "адвокат",
    "юридические консультации",
)


def _rendered(text: str) -> str:
    """The HTML a Jinja `{{ text }}` interpolation produces under
    autoescape — apostrophes/quotes/angle brackets become entities."""
    return str(escape(text))


def _iter_site_strings(value):
    """Yield every leaf string in a loaded site.json/projects.json dict."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_site_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_site_strings(item)


def _all_content_text(lang: str) -> str:
    text = " ".join(_iter_site_strings(load_site_content(lang)))
    text += " " + " ".join(_iter_site_strings(load_projects_content(lang)))
    return text


class ProvisionalFlagTests(unittest.TestCase):
    """1: every shipped content file has provisional == false."""

    def test_site_and_projects_json_are_not_provisional(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang, file="site.json"):
                self.assertFalse(load_site_content(lang)["provisional"])
            with self.subTest(lang=lang, file="projects.json"):
                self.assertFalse(load_projects_content(lang)["provisional"])


class NoVisibleProvisionalNoticeTests(unittest.TestCase):
    """2: no visible provisional notice appears on any public page."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_provisional_notice_absent_from_every_public_page(self):
        en_slug = load_projects_content("en")["projects"][0]["slug"]
        ru_slug = load_projects_content("ru")["projects"][0]["slug"]
        routes = {
            "en": ["/en/", "/en/about", "/en/expertise", "/en/projects",
                   f"/en/projects/{en_slug}", "/en/experience", "/en/contact",
                   "/en/ai-guide"],
            "ru": ["/ru/", "/ru/about", "/ru/expertise", "/ru/projects",
                   f"/ru/projects/{ru_slug}", "/ru/experience", "/ru/contact",
                   "/ru/ai-guide"],
        }
        for lang, paths in routes.items():
            for path in paths:
                with self.subTest(path=path):
                    body = self.client.get(path).data
                    self.assertNotIn(b"public-provisional-notice", body)


class HomePageSectionTests(unittest.TestCase):
    """3, 10: required Home sections (now four direction cards) render in
    both languages, and the featured-projects section lists exactly the
    three approved project ids."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_home_required_sections_render(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                site = load_site_content(lang)
                home = site["pages"]["home"]
                body = self.client.get(f"/{lang}/").data.decode("utf-8")
                for text in (
                    home["eyebrow"], home["heading"], home["intro"],
                    home["supporting_text"], home["cta_primary"],
                    home["cta_secondary"], home["featured_heading"],
                    home["featured_intro"], home["closing_heading"],
                    home["closing_text"],
                ):
                    self.assertIn(_rendered(text), body)
                self.assertEqual(len(home["directions"]), 4)
                for direction in home["directions"]:
                    self.assertIn(_rendered(direction["title"]), body)
                    self.assertIn(_rendered(direction["text"]), body)

    def test_home_features_exactly_three_approved_project_ids(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                site = load_site_content(lang)
                self.assertEqual(
                    site["pages"]["home"]["featured_project_ids"],
                    HOME_FEATURED_PROJECT_IDS,
                )
                projects_by_id = {
                    p["id"]: p for p in load_projects_content(lang)["projects"]
                }
                body = self.client.get(f"/{lang}/").data.decode("utf-8")
                for project_id in HOME_FEATURED_PROJECT_IDS:
                    slug = projects_by_id[project_id]["slug"]
                    self.assertIn(f"/{lang}/projects/{slug}", body)
                other_ids = APPROVED_PROJECT_IDS - set(HOME_FEATURED_PROJECT_IDS)
                for project_id in other_ids:
                    slug = projects_by_id[project_id]["slug"]
                    self.assertNotIn(f"/{lang}/projects/{slug}", body)


class AboutPageSectionTests(unittest.TestCase):
    """4: About renders exactly five sections in both languages."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_about_sections_render(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                page = load_site_content(lang)["pages"]["about"]
                body = self.client.get(f"/{lang}/about").data.decode("utf-8")
                self.assertIn(_rendered(page["heading"]), body)
                self.assertIn(_rendered(page["intro"]), body)
                self.assertIn(_rendered(page["closing"]), body)
                self.assertEqual(len(page["sections"]), 5)
                for section in page["sections"]:
                    self.assertIn(_rendered(section["title"]), body)
                    self.assertIn(_rendered(section["body"]), body)


class ExpertisePageSectionTests(unittest.TestCase):
    """5: Expertise renders exactly four pillars and all capability lists
    in both languages."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_expertise_pillars_and_capabilities_render(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                page = load_site_content(lang)["pages"]["expertise"]
                body = self.client.get(f"/{lang}/expertise").data.decode("utf-8")
                self.assertIn(_rendered(page["closing_heading"]), body)
                self.assertIn(_rendered(page["closing_text"]), body)
                self.assertEqual(len(page["pillars"]), 4)
                for pillar in page["pillars"]:
                    self.assertIn(_rendered(pillar["title"]), body)
                    self.assertIn(_rendered(pillar["description"]), body)
                    for capability in pillar["capabilities"]:
                        self.assertIn(_rendered(capability), body)


class ExpertiseAreasOfWorkRenameTests(unittest.TestCase):
    """1-8: the /expertise page's public-facing label changed from
    Экспертиза/Expertise to Направления/Areas of work, while the route
    path, endpoint name and JSON key stay "expertise" — this is a copy
    change only, never a technical rename."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_route_and_endpoint_are_unchanged(self):
        rules = {rule.endpoint: rule.rule for rule in self.app.url_map.iter_rules()}
        self.assertIn("public.expertise", rules)
        self.assertEqual(rules["public.expertise"], "/<any(en, ru):lang>/expertise")

    def test_ru_expertise_route_returns_200(self):
        self.assertEqual(self.client.get("/ru/expertise").status_code, 200)

    def test_en_expertise_route_returns_200(self):
        self.assertEqual(self.client.get("/en/expertise").status_code, 200)

    def test_russian_navigation_displays_napravleniya(self):
        nav = load_site_content("ru")["nav"]
        self.assertEqual(nav["expertise"], "Направления")
        body = self.client.get("/ru/").data.decode("utf-8")
        self.assertIn(">Направления<", body)

    def test_english_navigation_displays_areas_of_work(self):
        nav = load_site_content("en")["nav"]
        self.assertEqual(nav["expertise"], "Areas of work")
        body = self.client.get("/en/").data.decode("utf-8")
        self.assertIn(">Areas of work<", body)

    def test_russian_page_heading_is_napravleniya(self):
        body = self.client.get("/ru/expertise").data.decode("utf-8")
        self.assertIn("<h1>Направления</h1>", body)

    def test_english_page_heading_is_areas_of_work(self):
        body = self.client.get("/en/expertise").data.decode("utf-8")
        self.assertIn("<h1>Areas of work</h1>", body)

    def test_old_russian_label_absent_from_nav_and_heading(self):
        for path in ("/ru/", "/ru/expertise"):
            with self.subTest(path=path):
                body = self.client.get(path).data.decode("utf-8")
                self.assertNotIn("Экспертиза", body)

    def test_old_english_label_absent_from_nav_and_heading(self):
        for path in ("/en/", "/en/expertise"):
            with self.subTest(path=path):
                body = self.client.get(path).data.decode("utf-8")
                self.assertNotIn(">Expertise<", body)
                self.assertNotIn("<h1>Expertise</h1>", body)


class ExperiencePageSectionTests(unittest.TestCase):
    """6: Experience renders exactly six items in both languages."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_experience_stages_render(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                page = load_site_content(lang)["pages"]["experience"]
                body = self.client.get(f"/{lang}/experience").data.decode("utf-8")
                self.assertEqual(len(page["stages"]), 6)
                for stage in page["stages"]:
                    self.assertIn(_rendered(stage["title"]), body)
                    self.assertIn(_rendered(stage["text"]), body)


class ProjectCatalogueTests(unittest.TestCase):
    """5(selected)/7/8/12: exactly six selected projects per language,
    matching/unique ids and slugs, and each detail page still renders its
    title/focus/technologies after the copy rewrite."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_exactly_six_projects_per_language(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                projects = load_projects_content(lang)["projects"]
                self.assertEqual(len(projects), 6)
                self.assertEqual({p["id"] for p in projects}, APPROVED_PROJECT_IDS)

    def test_project_ids_and_slugs_match_across_languages(self):
        en = load_projects_content("en")["projects"]
        ru = load_projects_content("ru")["projects"]
        self.assertEqual({p["id"] for p in en}, {p["id"] for p in ru})
        self.assertEqual({p["slug"] for p in en}, {p["slug"] for p in ru})

    def test_project_ids_and_slugs_are_unique_per_language(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                projects = load_projects_content(lang)["projects"]
                ids = [p["id"] for p in projects]
                slugs = [p["slug"] for p in projects]
                self.assertEqual(len(ids), len(set(ids)))
                self.assertEqual(len(slugs), len(set(slugs)))

    def test_each_project_detail_page_renders_title_focus_and_technologies(self):
        for lang in SUPPORTED_LANGUAGES:
            for project in load_projects_content(lang)["projects"]:
                with self.subTest(lang=lang, slug=project["slug"]):
                    body = self.client.get(
                        f"/{lang}/projects/{project['slug']}"
                    ).data.decode("utf-8")
                    self.assertIn(_rendered(project["title"]), body)
                    self.assertIn(_rendered(project["focus"]), body)
                    for technology in project["technologies"]:
                        self.assertIn(_rendered(technology), body)


class PersonalExperimentsTests(unittest.TestCase):
    """6, 9, 10, 11, 14: exactly three experiments per language with
    matching/unique ids and preserved order, topics render, the Projects
    page shows both section headings, and experiments never produce a
    detail-page link (they have no slug/route)."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_exactly_three_experiments_per_language(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                experiments = load_projects_content(lang)["experiments"]
                self.assertEqual(len(experiments), 3)
                ids = [e["id"] for e in experiments]
                self.assertEqual(ids, APPROVED_EXPERIMENT_IDS)
                self.assertEqual(len(ids), len(set(ids)))

    def test_experiment_ids_match_and_preserve_order_across_languages(self):
        en_ids = [e["id"] for e in load_projects_content("en")["experiments"]]
        ru_ids = [e["id"] for e in load_projects_content("ru")["experiments"]]
        self.assertEqual(en_ids, ru_ids)

    def test_projects_page_shows_both_section_headings(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                page = load_site_content(lang)["pages"]["projects"]
                body = self.client.get(f"/{lang}/projects").data.decode("utf-8")
                self.assertIn(_rendered(page["selected_heading"]), body)
                self.assertIn(_rendered(page["selected_intro"]), body)
                self.assertIn(_rendered(page["experiments_heading"]), body)
                self.assertIn(_rendered(page["experiments_intro"]), body)

    def test_experiment_cards_render_title_summary_focus_and_topics(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                body = self.client.get(f"/{lang}/projects").data.decode("utf-8")
                for experiment in load_projects_content(lang)["experiments"]:
                    self.assertIn(_rendered(experiment["title"]), body)
                    self.assertIn(_rendered(experiment["summary"]), body)
                    self.assertIn(_rendered(experiment["focus"]), body)
                    for topic in experiment["topics"]:
                        self.assertIn(_rendered(topic), body)

    def test_experiments_do_not_produce_detail_page_links(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                body = self.client.get(f"/{lang}/projects").data.decode("utf-8")
                for experiment_id in APPROVED_EXPERIMENT_IDS:
                    self.assertNotIn(f'href="/{lang}/projects/{experiment_id}"', body)
                    # No detail route exists for an experiment id either.
                    response = self.client.get(f"/{lang}/projects/{experiment_id}")
                    self.assertEqual(response.status_code, 404)


class NoStaleOrOffLimitsCopyTests(unittest.TestCase):
    """12(project catalogue)/13/23: no old freelance-service *project*
    catalogue language and no current employer reference appears anywhere
    in the shipped content."""

    def test_no_old_project_ids_among_selected_projects(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                ids = {p["id"] for p in load_projects_content(lang)["projects"]}
                self.assertTrue(ids.isdisjoint(OLD_PROJECT_IDS))

    def test_no_old_project_titles_among_selected_projects(self):
        for lang in SUPPORTED_LANGUAGES:
            selected_text = " ".join(
                _iter_site_strings(load_projects_content(lang)["projects"])
            )
            for old_title in OLD_PROJECT_TITLES:
                with self.subTest(lang=lang, old_title=old_title):
                    self.assertNotIn(old_title, selected_text)

    def test_no_freelance_sales_language_in_content(self):
        for lang in SUPPORTED_LANGUAGES:
            all_text = _all_content_text(lang).lower()
            for phrase in FREELANCE_SALES_PHRASES:
                with self.subTest(lang=lang, phrase=phrase):
                    self.assertNotIn(phrase, all_text)

    def test_no_employer_reference_in_content(self):
        # No "employer" field exists anywhere in the approved schema, and
        # the approved copy never names Elena's current employer. This is
        # a regression guard against a future edit accidentally adding one.
        for lang in SUPPORTED_LANGUAGES:
            all_text = _all_content_text(lang).lower()
            self.assertNotIn("employer", all_text)
            self.assertNotIn("работодател", all_text)

    def test_no_therapy_or_counselling_claim_in_content(self):
        # Elena's interest in social psychology/conflict/negotiation is
        # framed as knowledge and practice, never as a clinical or
        # professional psychological service on offer.
        for lang in SUPPORTED_LANGUAGES:
            all_text = _all_content_text(lang).lower()
            for phrase in THERAPY_OR_COUNSELLING_PHRASES:
                with self.subTest(lang=lang, phrase=phrase):
                    self.assertNotIn(phrase, all_text)


class NoNotesOrFutureSectionPlaceholderTests(unittest.TestCase):
    """15: the site contains no visible Notes/blog/books/films/music
    placeholder or navigation item — that possibility stays out of scope
    for this implementation stage."""

    FORBIDDEN_NAV_WORDS = (
        "notes", "blog", "books", "films", "series", "music",
        "заметки", "блог", "книги", "фильмы", "музыка",
    )

    def test_nav_has_exactly_the_seven_approved_items(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                nav = load_site_content(lang)["nav"]
                self.assertEqual(
                    set(nav.keys()),
                    {"home", "about", "expertise", "projects", "experience",
                     "contact", "ai_guide"},
                )

    def test_no_forbidden_future_section_words_in_nav_values(self):
        for lang in SUPPORTED_LANGUAGES:
            nav = load_site_content(lang)["nav"]
            nav_text = " ".join(nav.values()).lower()
            for word in self.FORBIDDEN_NAV_WORDS:
                with self.subTest(lang=lang, word=word):
                    self.assertNotIn(word, nav_text)


class EditorialThemeCoverageTests(unittest.TestCase):
    """16, 17: the approved conflict/negotiation/social-psychology/
    experiments repositioning actually landed in both languages' content,
    not just in the task instructions."""

    def test_russian_content_covers_the_new_themes(self):
        text = _all_content_text("ru").lower()
        for term in ("конфликтолог", "переговор", "социальная психолог", "эксперимент"):
            with self.subTest(term=term):
                self.assertIn(term, text)

    def test_english_content_covers_the_new_themes(self):
        text = _all_content_text("en").lower()
        for term in ("conflict", "negotiation", "social psychology", "experiment"):
            with self.subTest(term=term):
                self.assertIn(term, text)


class AiGuideScopeTests(unittest.TestCase):
    """18, 19, 20: AI Guide's public scope notice is general-purpose (not
    legal-only), drops attorney-client/legal-advice-only framing, and
    states it cannot make commitments on Elena's behalf."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_scope_notice_is_general_not_legal_only(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                notice = load_site_content(lang)["pages"]["ai_guide"]["scope_notice"]
                general_marker = "any matter" if lang == "en" else "какому-либо вопросу"
                self.assertIn(general_marker, notice)

    def test_scope_notice_states_a_general_professional_advice_limitation(self):
        # 15: a general "does not replace a professional" limitation, not a
        # legal-advice-specific one.
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                notice = load_site_content(lang)["pages"]["ai_guide"]["scope_notice"]
                if lang == "en":
                    self.assertIn("do not replace advice from an appropriate professional", notice)
                else:
                    self.assertIn("не заменяют консультацию специалиста", notice)

    def test_no_legal_only_ai_guide_framing_in_content(self):
        for lang in SUPPORTED_LANGUAGES:
            page = load_site_content(lang)["pages"]["ai_guide"]
            page_text = " ".join(_iter_site_strings(page)).lower()
            for phrase in LEGAL_ONLY_AI_GUIDE_PHRASES:
                with self.subTest(lang=lang, phrase=phrase):
                    self.assertNotIn(phrase.lower(), page_text)

    def test_ai_guide_cannot_make_commitments_on_elenas_behalf(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                notice = load_site_content(lang)["pages"]["ai_guide"]["scope_notice"]
                marker = "on Elena's behalf" if lang == "en" else "от имени Елены"
                self.assertIn(marker, notice)


class EditorialPolishRenderTests(unittest.TestCase):
    """9-14: the exact approved copy edits from this final polish pass
    render correctly, and the retired "production-подобных" phrasing is
    gone from Russian content."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_no_production_podobnyy_in_russian_content(self):
        text = _all_content_text("ru")
        self.assertNotIn("production-подоб", text)

    def test_revised_russian_home_intro_renders(self):
        body = self.client.get("/ru/").data.decode("utf-8")
        expected = (
            "Здесь соединяются более 15 лет юридической практики, интерес к "
            "социальной психологии, конфликтологии и переговорам, работа с "
            "прикладным ИИ и автоматизацией, а также личные эксперименты с "
            "новыми инструментами."
        )
        self.assertIn(_rendered(expected), body)

    def test_revised_russian_about_intro_renders(self):
        body = self.client.get("/ru/about").data.decode("utf-8")
        expected = "Я не привыкла смотреть на задачи только через призму одной профессии."
        self.assertIn(_rendered(expected), body)

    def test_revised_english_about_intro_renders(self):
        body = self.client.get("/en/about").data.decode("utf-8")
        expected = "I rarely look at a problem through the lens of a single discipline."
        self.assertIn(_rendered(expected), body)

    def test_english_home_closing_uses_opposites(self):
        body = self.client.get("/en/").data.decode("utf-8")
        self.assertIn(
            _rendered("I do not see the human and the technical as opposites."), body
        )

    def test_revised_experiments_intro_renders(self):
        body = self.client.get("/en/projects").data.decode("utf-8")
        expected = (
            "without expecting every experiment to grow into a full-scale product."
        )
        self.assertIn(_rendered(expected), body)


class ContactAndAiGuideRenderTests(unittest.TestCase):
    """14, 15, 21: Contact supporting note and AI Guide scope notice render
    in both languages, and Contact wording covers cross-disciplinary topics
    rather than only the previous law/AI framing."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_contact_supporting_note_renders(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                page = load_site_content(lang)["pages"]["contact"]
                body = self.client.get(f"/{lang}/contact").data.decode("utf-8")
                self.assertIn(_rendered(page["supporting_note"]), body)

    def test_contact_covers_cross_disciplinary_topics(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                intro = load_site_content(lang)["pages"]["contact"]["intro"]
                marker = "cross-disciplinary" if lang == "en" else "междисциплинарных"
                self.assertIn(marker, intro)

    def test_ai_guide_scope_notice_and_items_render(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                page = load_site_content(lang)["pages"]["ai_guide"]
                body = self.client.get(f"/{lang}/ai-guide").data.decode("utf-8")
                self.assertIn(_rendered(page["scope_notice"]), body)
                self.assertIn(_rendered(page["scope_heading"]), body)
                for item in page["scope_items"]:
                    self.assertIn(_rendered(item), body)
                self.assertIn(_rendered(page["status_label"]), body)
                self.assertIn(_rendered(page["placeholder_message"]), body)


class NoSafeFilterInPublicTemplatesTests(unittest.TestCase):
    """25: `|safe` never appears in a public template."""

    def test_no_safe_filter_in_public_templates(self):
        template_files = sorted(PUBLIC_TEMPLATES_DIR.glob("*.html"))
        self.assertGreater(len(template_files), 0)
        for path in template_files:
            with self.subTest(template=path.name):
                self.assertNotIn("|safe", path.read_text(encoding="utf-8"))


class MetadataRenderingTests(unittest.TestCase):
    """17(metadata)/26: meta title/description render correctly in both
    languages, project-detail pages use the localized project title, and
    global metadata frames ElivCloud as Elena's personal project rather
    than treating the two names as interchangeable."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    PAGE_ROUTES = {
        "home": "/{lang}/",
        "about": "/{lang}/about",
        "expertise": "/{lang}/expertise",
        "projects": "/{lang}/projects",
        "experience": "/{lang}/experience",
        "contact": "/{lang}/contact",
        "ai_guide": "/{lang}/ai-guide",
    }

    def test_page_metadata_matches_content(self):
        for lang in SUPPORTED_LANGUAGES:
            site = load_site_content(lang)
            for page_key, route_template in self.PAGE_ROUTES.items():
                with self.subTest(lang=lang, page=page_key):
                    page = site["pages"][page_key]
                    body = self.client.get(
                        route_template.format(lang=lang)
                    ).data.decode("utf-8")
                    self.assertIn(
                        f"<title>{_rendered(page['meta_title'])}</title>", body
                    )
                    self.assertIn(
                        f'content="{_rendered(page["meta_description"])}"', body
                    )

    def test_home_meta_title_includes_name_and_site(self):
        # Checks the surname stem rather than a full "Elena Shlenskova"/
        # "Елена Шленскова" match: the RU title correctly uses the genitive
        # "Елены Шленсковой" ("ElivCloud — персональный проект Елены
        # Шленсковой"), not the nominative form.
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                meta_title = load_site_content(lang)["pages"]["home"]["meta_title"]
                self.assertIn("Shlenskova" if lang == "en" else "Шленсков", meta_title)
                self.assertIn("ElivCloud", meta_title)

    def test_metadata_frames_elivcloud_as_a_personal_project(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                site = load_site_content(lang)
                marker = "personal project" if lang == "en" else "персональный проект"
                self.assertIn(marker, site["meta"]["default_title"].lower())
                self.assertIn(marker, site["pages"]["home"]["meta_title"].lower())

    def test_project_detail_metadata_uses_localized_project_title(self):
        for lang in SUPPORTED_LANGUAGES:
            for project in load_projects_content(lang)["projects"]:
                with self.subTest(lang=lang, slug=project["slug"]):
                    body = self.client.get(
                        f"/{lang}/projects/{project['slug']}"
                    ).data.decode("utf-8")
                    self.assertIn(
                        f"<title>{_rendered(project['title'])} — ElivCloud</title>", body
                    )


if __name__ == "__main__":
    unittest.main()
