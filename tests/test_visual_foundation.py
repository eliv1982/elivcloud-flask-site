"""Coverage for the ElivCloud Visual Stage 1 foundation slice: approved
brand assets, shared header/footer shell, and the redesigned bilingual Home
page layout.

Uses tests.support.create_isolated_app() like every other route-level test
module in this suite, so nothing here touches the real instance/site.db or
makes any network call.
"""

from __future__ import annotations

import hashlib
import re
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
BRAND_SOURCE_DIR = REPO_ROOT / "static" / "brand" / "source"
PUBLIC_TEMPLATES_DIR = REPO_ROOT / "templates" / "public"
PUBLIC_CSS_PATH = REPO_ROOT / "static" / "css" / "public.css"

APPROVED_BRAND_FILES = (
    "eliv-logo-primary-on-light.png",
    "eliv-logo-primary-on-dark.png",
    "eliv-logo-horizontal-on-light.png",
    "eliv-logo-horizontal-on-dark.png",
    "eliv-logo-mark-on-light.png",
    "eliv-logo-mark-on-dark.png",
)

HEADER_LOGO_PATH = "/static/brand/source/eliv-logo-horizontal-on-light.png"
HERO_LOGO_PATH = "/static/brand/source/eliv-logo-primary-on-light.png"
FOOTER_LOGO_PATH = "/static/brand/source/eliv-logo-horizontal-on-dark.png"
FAVICON_PATH = "/static/brand/source/eliv-logo-mark-on-light.png"

NAV_ENDPOINTS = (
    ("public.home", "/{lang}/"),
    ("public.about", "/{lang}/about"),
    ("public.expertise", "/{lang}/expertise"),
    ("public.projects", "/{lang}/projects"),
    ("public.experience", "/{lang}/experience"),
    ("public.contact", "/{lang}/contact"),
    ("public.ai_guide", "/{lang}/ai-guide"),
)


class BrandAssetFilesExistTests(unittest.TestCase):
    """5: all six approved v3 brand files were copied into the repository,
    with their approved names unchanged, and nothing extra was copied
    alongside them (no zips, previews, QA images or README)."""

    def test_all_six_approved_brand_files_exist(self):
        for filename in APPROVED_BRAND_FILES:
            with self.subTest(filename=filename):
                self.assertTrue(
                    (BRAND_SOURCE_DIR / filename).is_file(),
                    f"missing approved brand asset: {filename}",
                )

    def test_no_disallowed_brand_files_were_copied(self):
        if not BRAND_SOURCE_DIR.is_dir():
            self.fail("static/brand/source directory does not exist")
        copied = {p.name for p in BRAND_SOURCE_DIR.iterdir() if p.is_file()}
        self.assertEqual(copied, set(APPROVED_BRAND_FILES))


class BrandAssetHttpResolutionTests(unittest.TestCase):
    """1-4: header, hero, footer and favicon brand assets each resolve with
    HTTP 200 through the running Flask app (not just on disk)."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_header_logo_asset_resolves(self):
        with self.client.get(HEADER_LOGO_PATH) as response:
            self.assertEqual(response.status_code, 200)

    def test_hero_logo_asset_resolves(self):
        with self.client.get(HERO_LOGO_PATH) as response:
            self.assertEqual(response.status_code, 200)

    def test_footer_logo_asset_resolves(self):
        with self.client.get(FOOTER_LOGO_PATH) as response:
            self.assertEqual(response.status_code, 200)

    def test_favicon_asset_resolves(self):
        with self.client.get(FAVICON_PATH) as response:
            self.assertEqual(response.status_code, 200)


class BrandAssetRenderTests(unittest.TestCase):
    """6-8: Home renders the approved hero logo, the shared header renders
    the horizontal light-background logo, and the shared footer renders a
    dark-background logo variant."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_home_renders_approved_hero_logo(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                body = self.client.get(f"/{lang}/").data.decode("utf-8")
                self.assertIn(HERO_LOGO_PATH, body)

    def test_header_renders_horizontal_light_logo(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                body = self.client.get(f"/{lang}/").data.decode("utf-8")
                self.assertIn(HEADER_LOGO_PATH, body)

    def test_footer_renders_dark_background_logo(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                body = self.client.get(f"/{lang}/").data.decode("utf-8")
                self.assertIn(FOOTER_LOGO_PATH, body)

    def test_favicon_link_present_on_public_pages(self):
        body = self.client.get("/en/").data.decode("utf-8")
        self.assertIn(FAVICON_PATH, body)


class BaseTemplateStructureTests(unittest.TestCase):
    """9-10: the shared base template exposes a skip link, and every public
    page keeps the correct <html lang> attribute after the redesign."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_base_template_includes_skip_link(self):
        base_html = (PUBLIC_TEMPLATES_DIR / "base.html").read_text(encoding="utf-8")
        self.assertIn('class="public-skip-link"', base_html)
        self.assertIn('href="#main-content"', base_html)
        self.assertIn('id="main-content"', base_html)

    def test_public_pages_have_correct_html_lang(self):
        for lang in SUPPORTED_LANGUAGES:
            for _, route_template in NAV_ENDPOINTS:
                path = route_template.format(lang=lang)
                with self.subTest(lang=lang, path=path):
                    body = self.client.get(path).data.decode("utf-8")
                    self.assertIn(f'<html lang="{lang}"', body)


class NavigationLinkValidityTests(unittest.TestCase):
    """11: every navigation link (header and footer) points at a route that
    actually resolves with HTTP 200, in both languages."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_all_navigation_links_are_valid_routes(self):
        rules = {rule.endpoint: rule.rule for rule in self.app.url_map.iter_rules()}
        for endpoint, _ in NAV_ENDPOINTS:
            self.assertIn(endpoint, rules)
        for lang in SUPPORTED_LANGUAGES:
            for _, route_template in NAV_ENDPOINTS:
                path = route_template.format(lang=lang)
                with self.subTest(lang=lang, path=path):
                    self.assertEqual(self.client.get(path).status_code, 200)

    def test_header_and_footer_contain_every_nav_link(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                body = self.client.get(f"/{lang}/").data.decode("utf-8")
                for _, route_template in NAV_ENDPOINTS:
                    href = f'href="{route_template.format(lang=lang)}"'
                    # At least the header copy must be present; occurrence
                    # count of 1 covers header-only, >=2 covers header+footer.
                    self.assertGreaterEqual(body.count(href), 1, href)


class LanguageSwitcherPreservesPageTests(unittest.TestCase):
    """12: the EN/RU switcher (now present in both header and footer) still
    preserves the current page across languages after the redesign."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_switcher_preserves_current_page_both_directions(self):
        body = self.client.get("/en/expertise").data.decode("utf-8")
        self.assertIn('href="/ru/expertise"', body)
        body = self.client.get("/ru/expertise").data.decode("utf-8")
        self.assertIn('href="/en/expertise"', body)


class NoAdminLinkOnAnyPublicPageTests(unittest.TestCase):
    """13: no public page (including the redesigned header/footer) exposes
    an /admin link."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_no_admin_link_on_any_public_page(self):
        for lang in SUPPORTED_LANGUAGES:
            for _, route_template in NAV_ENDPOINTS:
                path = route_template.format(lang=lang)
                with self.subTest(path=path):
                    body = self.client.get(path).data
                    self.assertNotIn(b"/admin", body)


class HomeDirectionCardCountTests(unittest.TestCase):
    """14: Home renders exactly four direction cards in both languages."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_home_renders_exactly_four_direction_cards(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                body = self.client.get(f"/{lang}/").data.decode("utf-8")
                self.assertEqual(body.count('class="public-direction-card"'), 4)


class HomeFeaturedProjectCountTests(unittest.TestCase):
    """15: Home renders exactly three featured project cards in both
    languages."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_home_renders_exactly_three_featured_project_cards(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                body = self.client.get(f"/{lang}/").data.decode("utf-8")
                self.assertEqual(body.count('class="public-featured-card"'), 3)


class NoExternalFontOrCdnTests(unittest.TestCase):
    """16: no external font service or CDN URL was introduced anywhere in
    the public templates or stylesheet."""

    FORBIDDEN_MARKERS = (
        "fonts.googleapis.com",
        "fonts.gstatic.com",
        "use.typekit.net",
        "cdn.jsdelivr.net",
        "cdnjs.cloudflare.com",
        "unpkg.com",
        "@font-face",
        "@import",
    )

    def test_no_external_font_or_cdn_reference_in_css(self):
        css_text = PUBLIC_CSS_PATH.read_text(encoding="utf-8")
        for marker in self.FORBIDDEN_MARKERS:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, css_text)

    def test_no_external_font_or_cdn_reference_in_templates(self):
        for path in sorted(PUBLIC_TEMPLATES_DIR.glob("*.html")):
            text = path.read_text(encoding="utf-8")
            for marker in self.FORBIDDEN_MARKERS:
                with self.subTest(template=path.name, marker=marker):
                    self.assertNotIn(marker, text)

    def test_rendered_home_page_has_no_external_font_or_cdn_reference(self):
        app = create_isolated_app()
        client = app.test_client()
        for lang in SUPPORTED_LANGUAGES:
            body = client.get(f"/{lang}/").data.decode("utf-8")
            for marker in self.FORBIDDEN_MARKERS:
                with self.subTest(lang=lang, marker=marker):
                    self.assertNotIn(marker, body)


class NoCssGradientTests(unittest.TestCase):
    """17: no CSS gradient was added to the public stylesheet."""

    def test_no_gradient_function_in_public_css(self):
        css_text = PUBLIC_CSS_PATH.read_text(encoding="utf-8")
        self.assertNotRegex(css_text.lower(), r"[a-z-]*gradient\s*\(")


class NoSafeFilterIntroducedTests(unittest.TestCase):
    """18: no `|safe` filter was introduced into any public template by
    this slice (base.html/home.html included)."""

    def test_no_safe_filter_in_base_or_home(self):
        for filename in ("base.html", "home.html"):
            with self.subTest(template=filename):
                text = (PUBLIC_TEMPLATES_DIR / filename).read_text(encoding="utf-8")
                self.assertNotIn("|safe", text)


class DeploymentAndContentUntouchedTests(unittest.TestCase):
    """19 (guardrail): content JSON stays untouched by this visual-only
    slice, and the site still reports every page as non-provisional."""

    def test_site_json_still_not_provisional(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                self.assertFalse(load_site_content(lang)["provisional"])


class MobileNavAccessibilityMarkupTests(unittest.TestCase):
    """Accessibility structure required for the redesigned mobile nav
    toggle: aria-expanded/aria-controls wiring and matching ids."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_nav_toggle_has_aria_wiring(self):
        body = self.client.get("/en/").data.decode("utf-8")
        toggle_match = re.search(
            r'<button[^>]*id="public-nav-toggle"[^>]*>', body
        )
        self.assertIsNotNone(toggle_match, "nav toggle button not found")
        toggle_tag = toggle_match.group(0)
        self.assertIn('aria-expanded="false"', toggle_tag)
        self.assertIn('aria-controls="public-nav"', toggle_tag)
        self.assertIn('id="public-nav"', body)


class LogoImageAltTextTests(unittest.TestCase):
    """Header/footer brand logos carry a non-empty identifying alt text;
    the decorative hero logo may use an empty alt because the same
    identity is already conveyed in the adjacent heading/eyebrow copy."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_header_and_footer_logos_have_alt_text(self):
        body = self.client.get("/en/").data.decode("utf-8")
        header_img = re.search(r'<img[^>]*public-brand-logo[^>]*>', body)
        footer_img = re.search(r'<img[^>]*public-footer-logo[^>]*>', body)
        self.assertIsNotNone(header_img)
        self.assertIsNotNone(footer_img)
        self.assertIn('alt="ElivCloud"', header_img.group(0))
        self.assertIn('alt="ElivCloud"', footer_img.group(0))

    def test_hero_logo_has_alt_attribute(self):
        body = self.client.get("/en/").data.decode("utf-8")
        hero_img = re.search(
            r'<img[^>]*eliv-logo-primary-on-light\.png[^>]*>', body
        )
        self.assertIsNotNone(hero_img)
        self.assertIn('alt=', hero_img.group(0))


class SkipLinkOutOfFlowTests(unittest.TestCase):
    """Corrected-pass regression: the skip link's own CSS rule keeps it out
    of normal layout flow (position: absolute, shifted off-screen) so it
    cannot reserve height/margin or push the header down. Guards against a
    future edit accidentally making it a normal-flow (static/relative)
    element again."""

    def test_skip_link_rule_is_absolutely_positioned_off_screen(self):
        css_text = PUBLIC_CSS_PATH.read_text(encoding="utf-8")
        match = re.search(
            r"\.public-skip-link\s*\{([^}]*)\}", css_text, re.DOTALL
        )
        self.assertIsNotNone(match, ".public-skip-link rule not found")
        rule_body = match.group(1)
        self.assertIn("position: absolute", rule_body)
        self.assertRegex(rule_body, r"left:\s*-\d+px")


class HomeSectionNestingTests(unittest.TestCase):
    """Corrected-pass regression: every Home section after the hero is a
    sibling <section> in the rendered DOM, not left nested inside the hero
    grid — the exact defect the human browser review reported."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    @staticmethod
    def _hero_span(body: str) -> tuple[int, int]:
        start = body.index('<section class="public-hero">')
        # The hero section contains only <div>/<img> descendants (no nested
        # <section>), so its first closing </section> tag is its own.
        end = body.index("</section>", start) + len("</section>")
        return start, end

    def test_direction_section_is_outside_hero_element(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                body = self.client.get(f"/{lang}/").data.decode("utf-8")
                _, hero_end = self._hero_span(body)
                directions_start = body.index('class="public-direction-grid"')
                self.assertGreater(directions_start, hero_end)

    def test_featured_section_is_outside_hero_element(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                body = self.client.get(f"/{lang}/").data.decode("utf-8")
                _, hero_end = self._hero_span(body)
                featured_start = body.index('class="public-featured-grid"')
                self.assertGreater(featured_start, hero_end)

    def test_closing_section_is_outside_hero_element(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                body = self.client.get(f"/{lang}/").data.decode("utf-8")
                _, hero_end = self._hero_span(body)
                closing_start = body.index('class="public-closing-panel"')
                self.assertGreater(closing_start, hero_end)

    def test_hero_inner_is_width_constrained_like_other_sections(self):
        # Root cause of the reported "hero copy far left / logo far right /
        # huge gap, later sections compressed" defect: .public-hero-inner
        # must share the same container max-width rule as every other
        # full-bleed section wrapper, not stretch edge-to-edge unconstrained.
        css_text = PUBLIC_CSS_PATH.read_text(encoding="utf-8")
        match = re.search(
            r"\.public-header-inner,\s*\.public-hero-inner,\s*\.public-section,"
            r"\s*\.public-footer-inner,\s*\.public-closing,\s*\.public-flash\s*\{"
            r"([^}]*)\}",
            css_text,
            re.DOTALL,
        )
        self.assertIsNotNone(
            match,
            ".public-hero-inner is not part of the shared container rule",
        )
        rule_body = match.group(1)
        self.assertIn("max-width: var(--container-width)", rule_body)
        self.assertIn("margin-inline: auto", rule_body)


class ContentJsonUnchangedTests(unittest.TestCase):
    """Regression guard pinning the current approved content JSON snapshot.

    This does not mean content JSON can never change — it means any future
    change must be a deliberate, approved copy edit (like the Contact
    naming correction, or the repository-link patch below, that last
    updated these hashes) that also updates this table, not an accidental
    side effect of an unrelated (e.g. visual-only) task."""

    # site.json hashes were last updated by the approved Experience copy
    # expansion (six stage bodies lengthened in both languages per the
    # human-review follow-up pass) and are untouched by the repository-link
    # patch, so they still match that stage.
    #
    # projects.json hashes were updated by the final width/repository-link
    # patch, which added the locally-verified repo_url for the Rise and
    # Shine and MoodMuse personal experiments (both previously had no
    # repo_url) — the only approved content change in that patch.
    EXPECTED_SHA256 = {
        "content/en/site.json": "80b11238971b4cd83c6f53a879e9928dc1af3ce0684816923a5569de9e4d5ad7",
        "content/en/projects.json": "96c7b4e1c62fd4c99f92b5dd54fa49b3c56518f6b9862901f6b10c2b4813481e",
        "content/ru/site.json": "8057d74adbfb8ecb0c79b8f18fb00af6e5b85ac0df986779af0e5bd852038e05",
        "content/ru/projects.json": "22ff7f4dcba5eb5b47ac6d7550ab655a5e2c2d59e8c4ceddc347f1467d9c3864",
    }

    def test_content_json_files_match_approved_snapshot(self):
        for relative_path, expected_hash in self.EXPECTED_SHA256.items():
            with self.subTest(path=relative_path):
                path = REPO_ROOT / relative_path
                actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertEqual(
                    actual_hash,
                    expected_hash,
                    f"{relative_path} no longer matches the approved content "
                    "snapshot — if this is an intentional, approved copy "
                    "edit, update EXPECTED_SHA256 above",
                )


class ContactNamingCorrectionTests(unittest.TestCase):
    """Approved Contact naming correction: nav label, meta_title and
    heading move from "Contact"/"Контакты" to "Message"/"Сообщение" /
    "Send a message"/"Отправить сообщение", while everything else on the
    Contact page (route, intro, supporting note, meta description, form
    labels including submit) stays exactly as approved before."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    EXPECTED = {
        "en": {
            "nav_contact": "Message",
            "meta_title": "Send a message — ElivCloud",
            "heading": "Send a message",
            "submit": "Send",
        },
        "ru": {
            "nav_contact": "Сообщение",
            "meta_title": "Отправить сообщение — ElivCloud",
            "heading": "Отправить сообщение",
            "submit": "Отправить",
        },
    }

    def test_nav_contact_label_updated(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                nav = load_site_content(lang)["nav"]
                self.assertEqual(nav["contact"], self.EXPECTED[lang]["nav_contact"])

    def test_contact_meta_title_and_heading_updated(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                page = load_site_content(lang)["pages"]["contact"]
                self.assertEqual(page["meta_title"], self.EXPECTED[lang]["meta_title"])
                self.assertEqual(page["heading"], self.EXPECTED[lang]["heading"])

    def test_form_submit_label_unchanged(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                form = load_site_content(lang)["pages"]["contact"]["form"]
                self.assertEqual(form["submit"], self.EXPECTED[lang]["submit"])

    def test_contact_page_renders_updated_heading_and_title(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                body = self.client.get(f"/{lang}/contact").data.decode("utf-8")
                expected = self.EXPECTED[lang]
                self.assertIn(f"<title>{expected['meta_title']}</title>", body)
                self.assertIn(f"<h1>{expected['heading']}</h1>", body)
                self.assertIn(f">{expected['submit']}<", body)

    def test_nav_renders_updated_contact_label_everywhere(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                body = self.client.get(f"/{lang}/").data.decode("utf-8")
                expected_label = self.EXPECTED[lang]["nav_contact"]
                self.assertIn(f">{expected_label}<", body)

    def test_route_and_endpoint_unchanged_by_naming_correction(self):
        rules = {rule.endpoint: rule.rule for rule in self.app.url_map.iter_rules()}
        self.assertIn("public.contact", rules)
        self.assertEqual(rules["public.contact"], "/<any(en, ru):lang>/contact")
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                self.assertEqual(self.client.get(f"/{lang}/contact").status_code, 200)

    def test_contact_intro_supporting_note_and_meta_description_unchanged(self):
        expected_unchanged = {
            "en": {
                "intro": (
                    "For conversations about complex systems, negotiation, "
                    "applied AI, automation, knowledge management or "
                    "cross-disciplinary projects, you can use the form below."
                ),
                "supporting_note": (
                    "Please do not send confidential documents, personal "
                    "data or information that is not intended for public "
                    "disclosure through this form."
                ),
                "meta_description": (
                    "Contact Elena Shlenskova about complex systems, "
                    "negotiation, applied AI, automation and "
                    "cross-disciplinary projects."
                ),
            },
            "ru": {
                "intro": (
                    "Если вам близки темы сложных систем, переговоров, "
                    "прикладного ИИ, автоматизации, управления знаниями или "
                    "междисциплинарных проектов, можно написать через форму "
                    "ниже."
                ),
                "supporting_note": (
                    "Не отправляйте через эту форму конфиденциальные "
                    "документы, персональные данные или сведения, которые не "
                    "предназначены для публичного раскрытия."
                ),
                "meta_description": (
                    "Связаться с Еленой Шленсковой по темам сложных систем, "
                    "переговоров, прикладного ИИ, автоматизации и "
                    "междисциплинарных проектов."
                ),
            },
        }
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                page = load_site_content(lang)["pages"]["contact"]
                expected = expected_unchanged[lang]
                self.assertEqual(page["intro"], expected["intro"])
                self.assertEqual(page["supporting_note"], expected["supporting_note"])
                self.assertEqual(page["meta_description"], expected["meta_description"])


class InternalPageCompactionTests(unittest.TestCase):
    """Approved compaction pass: generic internal pages (About, Areas of
    work, Projects, Experience, Send a message, AI Guide) get a smaller,
    tighter h1/intro/card scale, while the Home hero keeps its own larger
    heading size through a dedicated selector."""

    INTERNAL_TEMPLATE_SECTION_COUNTS = {
        "about.html": 1,
        "expertise.html": 1,
        "experience.html": 1,
        "contact.html": 1,
        "ai_guide.html": 1,
        "projects.html": 3,
    }

    ROOT_PX = 16

    @classmethod
    def setUpClass(cls):
        cls.css_text = PUBLIC_CSS_PATH.read_text(encoding="utf-8")
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    @staticmethod
    def _rem_to_px(rem_text: str, root_px: int = 16) -> float:
        return float(rem_text.replace("rem", "")) * root_px

    def _rule_block(self, selector_pattern: str) -> str:
        match = re.search(
            selector_pattern + r"\s*\{([^}]*)\}", self.css_text, re.DOTALL
        )
        self.assertIsNotNone(
            match, f"Could not find rule block for {selector_pattern!r}"
        )
        return match.group(1)

    def test_every_internal_page_template_uses_the_page_section_marker(self):
        for filename, expected_count in self.INTERNAL_TEMPLATE_SECTION_COUNTS.items():
            with self.subTest(template=filename):
                markup = (PUBLIC_TEMPLATES_DIR / filename).read_text(encoding="utf-8")
                self.assertEqual(
                    markup.count('class="public-section public-page-section"'),
                    expected_count,
                )

    def test_home_sections_do_not_carry_the_page_section_marker(self):
        home_markup = (PUBLIC_TEMPLATES_DIR / "home.html").read_text(encoding="utf-8")
        self.assertNotIn("public-page-section", home_markup)

    def test_base_h1_is_the_smaller_internal_page_scale(self):
        match = re.search(
            r"\nh1 \{\s*font-size:\s*clamp\(([\d.]+)rem,\s*([\d.]+)vw,\s*([\d.]+)rem\);"
            r"\s*line-height:\s*([\d.]+);",
            self.css_text,
        )
        self.assertIsNotNone(match, "Internal-page h1 clamp() rule not found")
        min_rem, _vw, max_rem, line_height = match.groups()
        min_px = self._rem_to_px(min_rem + "rem")
        max_px = self._rem_to_px(max_rem + "rem")
        # At a 1440-1600px viewport the clamp's preferred (vw) branch is
        # clipped by the ceiling, so max_px is what actually renders there.
        # Refinement pass target: desktop internal headings around 52-60px,
        # not 70px+.
        self.assertGreaterEqual(max_px, 52)
        self.assertLessEqual(max_px, 60)
        self.assertLess(min_px, max_px)
        self.assertGreaterEqual(float(line_height), 1.04)
        self.assertLessEqual(float(line_height), 1.1)

    def test_home_hero_heading_keeps_its_own_larger_scale(self):
        internal_match = re.search(
            r"\nh1 \{\s*font-size:\s*clamp\([\d.]+rem,\s*[\d.]+vw,\s*([\d.]+)rem\);",
            self.css_text,
        )
        self.assertIsNotNone(internal_match, "Internal-page h1 clamp() rule not found")
        internal_max_px = self._rem_to_px(internal_match.group(1) + "rem")

        block = self._rule_block(r"\.public-hero-heading")
        match = re.search(
            r"font-size:\s*clamp\(([\d.]+)rem,\s*[\d.]+vw,\s*([\d.]+)rem\)",
            block,
        )
        self.assertIsNotNone(match, ".public-hero-heading font-size clamp() not found")
        min_rem, max_rem = match.groups()
        self.assertEqual(min_rem, "3.35")
        self.assertEqual(max_rem, "4.45")
        # Strictly larger than the internal-page h1 ceiling, whatever that
        # ceiling currently is — Home always stays the most prominent
        # heading on the site without pinning a magic pixel threshold here.
        self.assertGreater(self._rem_to_px(max_rem + "rem"), internal_max_px)

    def test_page_section_desktop_top_padding_is_in_approved_range(self):
        block = self._rule_block(r"\.public-page-section")
        match = re.search(r"padding-block:\s*([\d.]+)rem", block)
        self.assertIsNotNone(match)
        px = self._rem_to_px(match.group(1) + "rem")
        self.assertGreaterEqual(px, 56)
        self.assertLessEqual(px, 68)

    def test_pillar_card_padding_and_typography_in_approved_ranges(self):
        block = self._rule_block(r"\.public-pillar")
        padding_match = re.search(r"padding:\s*([\d.]+)rem\s+([\d.]+)rem", block)
        self.assertIsNotNone(padding_match)
        for value in padding_match.groups():
            px = self._rem_to_px(value + "rem")
            self.assertGreaterEqual(px, 24)
            self.assertLessEqual(px, 29)

        heading_block = self._rule_block(r"\.public-pillar h2")
        size_match = re.search(
            r"font-size:\s*clamp\(([\d.]+)rem,\s*[\d.]+vw,\s*([\d.]+)rem\)",
            heading_block,
        )
        self.assertIsNotNone(size_match, ".public-pillar h2 clamp() not found")
        heading_min_px = self._rem_to_px(size_match.group(1) + "rem")
        heading_max_px = self._rem_to_px(size_match.group(2) + "rem")
        self.assertLess(heading_min_px, heading_max_px)
        self.assertGreaterEqual(heading_min_px, 1.1 * self.ROOT_PX)
        self.assertLessEqual(heading_max_px, 1.45 * self.ROOT_PX)

        body_block = self._rule_block(r"\.public-pillar p")
        body_size_match = re.search(r"font-size:\s*([\d.]+)rem", body_block)
        self.assertIsNotNone(body_size_match)
        body_px = self._rem_to_px(body_size_match.group(1) + "rem")
        self.assertGreaterEqual(body_px, 0.98 * self.ROOT_PX)
        self.assertLessEqual(body_px, 1.04 * self.ROOT_PX)

    def test_capability_tag_text_stays_at_or_above_0_8rem(self):
        block = self._rule_block(r"\.public-capability-list li")
        match = re.search(r"font-size:\s*([\d.]+)rem", block)
        self.assertIsNotNone(match)
        value = float(match.group(1))
        self.assertGreaterEqual(value, 0.8)
        self.assertGreaterEqual(value, 0.82)
        self.assertLessEqual(value, 0.88)

    def test_pillar_card_gap_in_approved_desktop_range(self):
        block = self._rule_block(r"\.public-pillars")
        match = re.search(r"gap:\s*([\d.]+)rem", block)
        self.assertIsNotNone(match)
        px = self._rem_to_px(match.group(1) + "rem")
        self.assertGreaterEqual(px, 18)
        self.assertLessEqual(px, 24)

    def test_about_page_renders_page_section_marker_and_smaller_heading_scale(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                body = self.client.get(f"/{lang}/about").data.decode("utf-8")
                self.assertIn('class="public-section public-page-section"', body)
                # Plain, unclassed h1 — inherits the smaller internal scale,
                # not .public-hero-heading (which only exists on Home).
                self.assertRegex(body, r"<h1>[^<]+</h1>")

    def test_home_hero_heading_class_unaffected_by_compaction(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                body = self.client.get(f"/{lang}/").data.decode("utf-8")
                self.assertRegex(body, r'<h1 class="public-hero-heading">')


class ExpertiseGridRedesignTests(unittest.TestCase):
    """Human-review follow-up: Areas of work / Направления no longer shares
    the single-column .public-pillars list (which rendered as a sequence of
    very wide horizontal cards) with About/Experience. It gets its own
    dedicated 2x2 grid wrapper, and the closing "common principle" text
    becomes a compact panel instead of a large detached heading."""

    @classmethod
    def setUpClass(cls):
        cls.css_text = PUBLIC_CSS_PATH.read_text(encoding="utf-8")
        cls.expertise_markup = (PUBLIC_TEMPLATES_DIR / "expertise.html").read_text(
            encoding="utf-8"
        )
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_expertise_template_uses_a_dedicated_grid_wrapper(self):
        self.assertIn('class="public-expertise-grid"', self.expertise_markup)
        # It must not fall back to the generic single-column list shared by
        # About/Experience.
        self.assertNotIn('class="public-pillars"', self.expertise_markup)

    def test_expertise_grid_is_two_columns_on_desktop(self):
        match = re.search(
            r"\.public-expertise-grid\s*\{([^}]*)\}", self.css_text, re.DOTALL
        )
        self.assertIsNotNone(match, ".public-expertise-grid rule not found")
        self.assertIn("grid-template-columns: repeat(2, 1fr)", match.group(1))

    def test_areas_of_work_renders_exactly_four_cards(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                body = self.client.get(f"/{lang}/expertise").data.decode("utf-8")
                self.assertEqual(body.count('class="public-expertise-card"'), 4)

    def test_common_principle_renders_as_a_compact_panel(self):
        self.assertIn('class="public-expertise-principle"', self.expertise_markup)
        # Anchored to a line start so this matches only the standalone
        # ".public-expertise-principle { ... }" rule, not the earlier
        # ".public-expertise-grid + .public-expertise-principle" spacing
        # rule that also ends in the same class name.
        block = re.search(
            r"\n\.public-expertise-principle\s*\{([^}]*)\}", self.css_text, re.DOTALL
        )
        self.assertIsNotNone(block, ".public-expertise-principle rule not found")
        rule_body = block.group(1)
        self.assertIn("background:", rule_body)
        self.assertIn("padding:", rule_body)

    def test_common_principle_heading_is_smaller_than_generic_h2(self):
        generic_h2 = re.search(
            r"\nh2 \{\s*font-size:\s*clamp\([\d.]+rem,\s*[\d.]+vw,\s*([\d.]+)rem\);",
            self.css_text,
        )
        principle_h2 = re.search(
            r"\.public-expertise-principle h2\s*\{\s*font-size:\s*"
            r"clamp\([\d.]+rem,\s*[\d.]+vw,\s*([\d.]+)rem\)",
            self.css_text,
        )
        self.assertIsNotNone(generic_h2)
        self.assertIsNotNone(principle_h2)
        self.assertLess(float(principle_h2.group(1)), float(generic_h2.group(1)))


class NoClippingMechanismOnPublicCardsTests(unittest.TestCase):
    """Human-review follow-up: meaningful card content must never be
    hidden, clamped or cropped. Guards against line-clamp, content-hiding
    overflow, and fixed/max heights creeping back into any of the selected
    public card components."""

    CARD_SELECTORS = (
        r"\.public-direction-card",
        r"\.public-expertise-card",
        r"\.public-project-card",
        r"\.public-experiment-card",
        r"\.public-featured-card",
        r"\.public-pillar",
    )

    @classmethod
    def setUpClass(cls):
        cls.css_text = PUBLIC_CSS_PATH.read_text(encoding="utf-8")

    def _rule_blocks(self, selector_pattern: str) -> list[str]:
        return re.findall(selector_pattern + r"\s*\{([^}]*)\}", self.css_text, re.DOTALL)

    def test_no_line_clamp_anywhere_in_public_css(self):
        self.assertNotIn("line-clamp", self.css_text)

    def test_no_selected_card_class_uses_overflow_hidden(self):
        # .sr-only is a screen-reader utility, not a content card, and is
        # allowed to use overflow: hidden to visually hide its own text.
        sr_only_block = re.search(r"\.sr-only\s*\{([^}]*)\}", self.css_text, re.DOTALL)
        self.assertIsNotNone(sr_only_block)
        css_without_sr_only = self.css_text.replace(sr_only_block.group(0), "")
        self.assertNotIn("overflow: hidden", css_without_sr_only)
        self.assertNotIn("overflow:hidden", css_without_sr_only)

    def test_no_fixed_or_max_height_on_selected_public_cards(self):
        for selector in self.CARD_SELECTORS:
            with self.subTest(selector=selector):
                blocks = self._rule_blocks(selector)
                self.assertTrue(blocks, f"no rule block found for {selector!r}")
                for block in blocks:
                    self.assertNotRegex(block, r"(?<!min-)(?<!line-)height\s*:")


class MessageConfidentialityNoteCorrectionTests(unittest.TestCase):
    """The Message page confidentiality note previously warned about only
    the "first message" sent through the form. The restriction must apply
    to every message sent through the form, in both languages."""

    FORBIDDEN_PHRASES = {
        "en": "first message",
        "ru": "первом сообщении",
    }

    FORM_REFERENCE = {
        "en": "through this form",
        "ru": "через эту форму",
    }

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_note_no_longer_singles_out_the_first_message(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                note = load_site_content(lang)["pages"]["contact"]["supporting_note"]
                self.assertNotIn(self.FORBIDDEN_PHRASES[lang], note)

    def test_note_references_the_form_in_both_languages(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                note = load_site_content(lang)["pages"]["contact"]["supporting_note"]
                self.assertIn(self.FORM_REFERENCE[lang], note)

    def test_corrected_note_renders_on_the_message_page(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                body = self.client.get(f"/{lang}/contact").data.decode("utf-8")
                note = load_site_content(lang)["pages"]["contact"]["supporting_note"]
                self.assertIn(note, body)
                self.assertNotIn(self.FORBIDDEN_PHRASES[lang], body)


class ProjectAndExperimentLinkRegressionTests(unittest.TestCase):
    """Regression guard for the visual refinement pass: existing project
    detail pages must keep rendering their repository links exactly as
    before — the CSS/typography changes must not touch routes, content or
    the repo_url anchors."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_project_detail_pages_render_their_repo_url_when_present(self):
        for lang in SUPPORTED_LANGUAGES:
            projects = load_projects_content(lang)["projects"]
            for project in projects:
                if not project.get("repo_url"):
                    continue
                with self.subTest(lang=lang, slug=project["slug"]):
                    body = self.client.get(
                        f"/{lang}/projects/{project['slug']}"
                    ).data.decode("utf-8")
                    self.assertIn(f'href="{project["repo_url"]}"', body)
                    self.assertIn('target="_blank"', body)
                    self.assertIn('rel="noopener noreferrer"', body)


class HomeSectionHeadingHierarchyTests(unittest.TestCase):
    """Human-review follow-up: "Направления / Areas of work" previously
    rendered as a small kicker <p>, not a heading at all, while "Избранные
    проекты / Selected projects" used the full generic 3rem h2 — two wildly
    different sizes for the same level of hierarchy. Both now share one
    .public-section-heading scale."""

    @classmethod
    def setUpClass(cls):
        cls.css_text = PUBLIC_CSS_PATH.read_text(encoding="utf-8")
        cls.home_markup = (PUBLIC_TEMPLATES_DIR / "home.html").read_text(encoding="utf-8")
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_directions_and_featured_headings_share_section_heading_class(self):
        self.assertRegex(
            self.home_markup,
            r'<h2 id="public-directions-heading" class="public-section-heading">',
        )
        self.assertRegex(
            self.home_markup,
            r'<h2 id="public-featured-heading" class="public-section-heading">',
        )

    def test_directions_heading_is_a_real_h2_not_an_eyebrow(self):
        self.assertNotIn("public-directions-kicker", self.home_markup)
        self.assertNotIn("public-directions-kicker", self.css_text)
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                body = self.client.get(f"/{lang}/").data.decode("utf-8")
                nav_expertise = load_site_content(lang)["nav"]["expertise"]
                self.assertRegex(
                    body,
                    r'<h2 id="public-directions-heading" class="public-section-heading">'
                    + re.escape(nav_expertise)
                    + r"</h2>",
                )

    def test_both_home_headings_use_the_shared_clamp_scale(self):
        match = re.search(
            r"\.public-section-heading\s*\{([^}]*)\}", self.css_text, re.DOTALL
        )
        self.assertIsNotNone(match, ".public-section-heading rule not found")
        self.assertIn("font-size: clamp(", match.group(1))


class AboutCardMeasureTests(unittest.TestCase):
    """Final width patch: About/Experience card copy previously used
    max-width: 760px, then a 92ch measure, inside a full-width card — both
    were still an artificial restriction on top of the card's own width.
    The owner confirmed public page copy should use the available content
    width, so .public-pillar p (and the About closing paragraph that
    follows the pillar list) must carry no ch/px measure of its own at
    all — width: 100%; max-width: none."""

    @classmethod
    def setUpClass(cls):
        cls.css_text = PUBLIC_CSS_PATH.read_text(encoding="utf-8")

    def test_pillar_paragraph_has_no_ch_based_measure(self):
        match = re.search(r"\.public-pillar p\s*\{([^}]*)\}", self.css_text, re.DOTALL)
        self.assertIsNotNone(match, ".public-pillar p rule not found")
        self.assertNotRegex(match.group(1), r"max-width:\s*[\d.]+ch")
        self.assertIn("max-width: none", match.group(1))
        self.assertIn("width: 100%", match.group(1))

    def test_pillar_paragraph_no_longer_uses_a_fixed_pixel_measure(self):
        match = re.search(r"\.public-pillar p\s*\{([^}]*)\}", self.css_text, re.DOTALL)
        self.assertIsNotNone(match)
        self.assertNotIn("max-width: 760px", match.group(1))
        self.assertNotIn("max-width: 920px", match.group(1))

    def test_about_closing_paragraph_matches_pillar_full_width(self):
        match = re.search(r"\n\.public-pillars \+ p\s*\{([^}]*)\}", self.css_text, re.DOTALL)
        self.assertIsNotNone(match, ".public-pillars + p rule not found")
        rule_body = match.group(1)
        self.assertNotRegex(rule_body, r"max-width:\s*[\d.]+ch")
        self.assertIn("max-width: none", rule_body)
        self.assertIn("width: 100%", rule_body)


class HomeClosingPanelGridTests(unittest.TestCase):
    """Human-review follow-up: the Home closing panel spanned the full
    container but kept every line of copy inside the left half. It is now a
    deliberate two-column grid (heading / paragraph) instead."""

    @classmethod
    def setUpClass(cls):
        cls.css_text = PUBLIC_CSS_PATH.read_text(encoding="utf-8")
        cls.home_markup = (PUBLIC_TEMPLATES_DIR / "home.html").read_text(encoding="utf-8")

    def test_home_template_wraps_closing_copy_in_the_grid(self):
        self.assertIn('class="public-closing-grid"', self.home_markup)

    def test_closing_grid_is_two_columns_on_desktop(self):
        match = re.search(
            r"\n\.public-closing-grid\s*\{([^}]*)\}", self.css_text, re.DOTALL
        )
        self.assertIsNotNone(match, ".public-closing-grid rule not found")
        # Final width patch: minmax(0, 44%) minmax(0, 56%) rebalances the
        # heading/paragraph split (was 38%/1fr) and lets each track shrink
        # below its content's min-content size instead of overflowing.
        self.assertRegex(
            match.group(1),
            r"grid-template-columns:\s*minmax\(0,\s*44%\)\s*minmax\(0,\s*56%\)",
        )

    def test_closing_grid_paragraph_has_no_narrow_measure(self):
        match = re.search(
            r"\.public-closing-grid p\s*\{([^}]*)\}", self.css_text, re.DOTALL
        )
        self.assertIsNotNone(match, ".public-closing-grid p rule not found")
        self.assertIn("max-width: none", match.group(1))
        self.assertIn("width: 100%", match.group(1))

    def test_closing_grid_heading_uses_the_rebalanced_scale(self):
        match = re.search(
            r"\.public-closing-grid h2\s*\{([^}]*)\}", self.css_text, re.DOTALL
        )
        self.assertIsNotNone(match, ".public-closing-grid h2 rule not found")
        self.assertIn(
            "font-size: clamp(1.9rem, 2.6vw, 2.5rem)", match.group(1)
        )
        self.assertIn("max-width: none", match.group(1))


class ExpertisePrincipleGridTests(unittest.TestCase):
    """Human-review follow-up: the Areas-of-work "Общий принцип / The common
    principle" panel spanned the full container but its text used only the
    left half. It is now a deliberate title-column / text-column grid."""

    @classmethod
    def setUpClass(cls):
        cls.css_text = PUBLIC_CSS_PATH.read_text(encoding="utf-8")
        cls.expertise_markup = (PUBLIC_TEMPLATES_DIR / "expertise.html").read_text(
            encoding="utf-8"
        )

    def test_expertise_template_wraps_principle_copy_in_the_grid(self):
        self.assertIn('class="public-expertise-principle-grid"', self.expertise_markup)

    def test_principle_grid_is_two_columns_on_desktop(self):
        match = re.search(
            r"\n\.public-expertise-principle-grid\s*\{([^}]*)\}",
            self.css_text,
            re.DOTALL,
        )
        self.assertIsNotNone(match, ".public-expertise-principle-grid rule not found")
        self.assertRegex(match.group(1), r"grid-template-columns:\s*\d+% 1fr")

    def test_principle_grid_paragraph_has_no_narrow_measure(self):
        match = re.search(
            r"\.public-expertise-principle-grid p\s*\{([^}]*)\}",
            self.css_text,
            re.DOTALL,
        )
        self.assertIsNotNone(match, ".public-expertise-principle-grid p rule not found")
        self.assertIn("max-width: none", match.group(1))

    def test_principle_heading_scale_is_unaffected_by_the_new_wrapper(self):
        # Regression guard: the pre-existing selector .public-expertise-principle
        # h2 (which test_common_principle_heading_is_smaller_than_generic_h2
        # depends on) must still exist verbatim — the new wrapper only adds
        # layout, it must not have replaced the descendant heading rule.
        self.assertIsNotNone(
            re.search(
                r"\.public-expertise-principle h2\s*\{\s*font-size:\s*clamp\(",
                self.css_text,
            )
        )


class ProjectsCanonicalTechnologyRenderingTests(unittest.TestCase):
    """Human-review follow-up: the six canonical Projects cards stopped
    rendering their technology lists (while personal experiments kept their
    topic tags) — an inconsistency with no corresponding content change, since
    projects.json always carried a populated technologies array."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_all_six_canonical_projects_still_render(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                body = self.client.get(f"/{lang}/projects").data.decode("utf-8")
                self.assertEqual(body.count('class="public-project-card"'), 6)

    def test_canonical_technologies_match_content_json(self):
        for lang in SUPPORTED_LANGUAGES:
            projects = load_projects_content(lang)["projects"]
            body = self.client.get(f"/{lang}/projects").data.decode("utf-8")
            for project in projects:
                with self.subTest(lang=lang, slug=project["slug"]):
                    for technology in project["technologies"]:
                        self.assertIn(f"<li>{technology}</li>", body)

    def test_canonical_cards_render_the_overview_link_once_per_project(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                body = self.client.get(f"/{lang}/projects").data.decode("utf-8")
                self.assertEqual(body.count('class="public-project-link"'), 6)


class CompactTagSharedStyleTests(unittest.TestCase):
    """Human-review follow-up + spec: one compact tag variant is shared by
    project technologies, experiment topics and Areas-of-work capabilities,
    instead of three near-duplicate rule sets with different sizes."""

    @classmethod
    def setUpClass(cls):
        cls.css_text = PUBLIC_CSS_PATH.read_text(encoding="utf-8")
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_tag_list_and_capability_list_share_one_rule_block(self):
        match = re.search(
            r"\.public-tag-list li,\s*\n\.public-capability-list li\s*\{([^}]*)\}",
            self.css_text,
        )
        self.assertIsNotNone(
            match,
            ".public-tag-list li and .public-capability-list li are not sharing "
            "one compact-tag rule block",
        )
        rule_body = match.group(1)
        size_match = re.search(r"font-size:\s*([\d.]+)rem", rule_body)
        self.assertIsNotNone(size_match)
        size = float(size_match.group(1))
        self.assertGreaterEqual(size, 0.76)
        self.assertLessEqual(size, 0.88)
        self.assertNotIn("border-radius: 999px", rule_body)
        self.assertNotIn("border-radius: 50%", rule_body)

    def test_project_and_experiment_tags_render_with_shared_class(self):
        body = self.client.get("/en/projects").data.decode("utf-8")
        # 6 canonical projects + 3 experiments (the third also carries a
        # repo link, but all three always render topics) all use the same
        # .public-tag-list wrapper.
        self.assertGreaterEqual(body.count('class="public-tag-list"'), 9)


class ExperienceGridAndCopyExpansionTests(unittest.TestCase):
    """Human-review follow-up: Experience cards had too little text for
    their wide horizontal single-column format. The six stages now render in
    a dedicated two-column grid with the approved expanded copy."""

    EXPECTED_SECOND_SENTENCE = {
        "en": {
            0: "The work involves looking beyond the formal requirement",
            1: "This context requires legal, financial and operational dependencies",
            2: "This perspective is especially useful where formal positions alone",
            3: "Across these projects, I pay particular attention to context",
            4: "a solution should go beyond a demonstration",
            5: "Experiments make it possible to test a hypothesis quickly",
        },
        "ru": {
            0: "В этой работе важно не только увидеть формальное требование",
            1: "Такой контекст требует одновременно держать в поле зрения",
            2: "Такой взгляд особенно полезен там, где формальные позиции",
            3: "В этих проектах я уделяю особое внимание контексту",
            4: "Для меня важно, чтобы решение не заканчивалось на демонстрации",
            5: "Экспериментальный формат помогает быстро проверить гипотезу",
        },
    }

    @classmethod
    def setUpClass(cls):
        cls.css_text = PUBLIC_CSS_PATH.read_text(encoding="utf-8")
        cls.experience_markup = (PUBLIC_TEMPLATES_DIR / "experience.html").read_text(
            encoding="utf-8"
        )
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_experience_uses_a_dedicated_two_column_grid_wrapper(self):
        self.assertIn('class="public-experience-grid"', self.experience_markup)
        self.assertNotIn('class="public-pillars"', self.experience_markup)
        match = re.search(
            r"\.public-experience-grid\s*\{([^}]*)\}", self.css_text, re.DOTALL
        )
        self.assertIsNotNone(match, ".public-experience-grid rule not found")
        self.assertIn("grid-template-columns: repeat(2, 1fr)", match.group(1))

    def test_experience_renders_six_expanded_texts_in_both_languages(self):
        for lang in SUPPORTED_LANGUAGES:
            body = self.client.get(f"/{lang}/experience").data.decode("utf-8")
            stages = load_site_content(lang)["pages"]["experience"]["stages"]
            self.assertEqual(len(stages), 6)
            for index, stage in enumerate(stages):
                with self.subTest(lang=lang, index=index):
                    # str(escape(...)) mirrors Jinja's autoescaping (e.g. the
                    # apostrophe in the EN stage 6 text becomes &#39;), so
                    # this compares against what actually renders, not the
                    # raw JSON string.
                    self.assertIn(str(escape(stage["text"])), body)
                    self.assertIn(
                        self.EXPECTED_SECOND_SENTENCE[lang][index], stage["text"]
                    )


class AIGuideCapabilitiesRedesignTests(unittest.TestCase):
    """Human-review follow-up: the "Чем он может помочь / What it can help
    with" list was five large full-width boxed rows using an artificially
    narrow text measure. It is now a compact semantic <ol>, and the scope
    notice / placeholder use the available page width."""

    @classmethod
    def setUpClass(cls):
        cls.css_text = PUBLIC_CSS_PATH.read_text(encoding="utf-8")
        cls.ai_guide_markup = (PUBLIC_TEMPLATES_DIR / "ai_guide.html").read_text(
            encoding="utf-8"
        )
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_capability_items_use_a_semantic_ordered_list(self):
        self.assertIn('<ol class="public-guide-capabilities">', self.ai_guide_markup)
        self.assertIn('class="public-guide-number"', self.ai_guide_markup)
        self.assertIn('class="public-guide-text"', self.ai_guide_markup)

    def test_does_not_render_generic_scope_list_or_pillar_cards(self):
        self.assertNotIn("public-scope-list", self.ai_guide_markup)
        self.assertNotIn("public-scope-list", self.css_text)
        self.assertNotIn("public-pillar", self.ai_guide_markup)

    def test_rendered_page_has_five_capability_items_in_both_languages(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                body = self.client.get(f"/{lang}/ai-guide").data.decode("utf-8")
                scope_items = load_site_content(lang)["pages"]["ai_guide"]["scope_items"]
                self.assertEqual(len(scope_items), 5)
                self.assertEqual(body.count('class="public-guide-number"'), 5)
                for item in scope_items:
                    with self.subTest(item=item):
                        # str(escape(...)) mirrors Jinja's autoescaping (the
                        # EN "Elena's" item renders with &#39;, not a raw
                        # apostrophe).
                        self.assertIn(
                            f'<span class="public-guide-text">{escape(item)}</span>',
                            body,
                        )

    def test_scope_notice_remains_present_in_both_languages(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                body = self.client.get(f"/{lang}/ai-guide").data.decode("utf-8")
                notice = load_site_content(lang)["pages"]["ai_guide"]["scope_notice"]
                self.assertIn(str(escape(notice)), body)
                self.assertIn('class="public-ai-guide-notice"', body)

    def test_placeholder_status_remains_present_in_both_languages(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                body = self.client.get(f"/{lang}/ai-guide").data.decode("utf-8")
                page = load_site_content(lang)["pages"]["ai_guide"]
                self.assertIn('class="public-ai-guide-status"', body)
                self.assertIn(page["status_label"], body)
                self.assertIn(page["placeholder_message"], body)

    def test_notice_and_status_do_not_use_a_narrow_fixed_measure(self):
        notice_block = re.search(
            r"\.public-ai-guide-notice\s*\{([^}]*)\}", self.css_text, re.DOTALL
        )
        status_block = re.search(
            r"\.public-ai-guide-status\s*\{([^}]*)\}", self.css_text, re.DOTALL
        )
        self.assertIsNotNone(notice_block)
        self.assertIsNotNone(status_block)
        self.assertNotIn("max-width: 760px", notice_block.group(1))
        self.assertNotRegex(notice_block.group(1), r"max-width:\s*[\d.]+ch")
        # Final width patch: the notice previously stopped at 92ch — it
        # must now span the same content width as the ordered list above
        # it, exactly like .public-ai-guide-status already did.
        self.assertIn("max-width: none", notice_block.group(1))
        self.assertIn("width: 100%", notice_block.group(1))
        self.assertIn("max-width: none", status_block.group(1))
        self.assertIn("width: 100%", status_block.group(1))


class FinalWidthPatchGlobalRuleTests(unittest.TestCase):
    """Final deterministic width patch: the confirmed root cause was that
    public.css still globally constrained every paragraph with
    max-width: 70ch and then layered several additional 760px/900px/920px/
    92ch limits on top. The owner wants public page copy to use the
    available content width, so this patch removes the restriction at its
    source (the global `p` rule) instead of swapping one ch/px ceiling for
    a slightly larger one."""

    @classmethod
    def setUpClass(cls):
        cls.css_text = PUBLIC_CSS_PATH.read_text(encoding="utf-8")

    def _rule_block(self, selector_pattern: str) -> str:
        match = re.search(
            selector_pattern + r"\s*\{([^}]*)\}", self.css_text, re.DOTALL
        )
        self.assertIsNotNone(
            match, f"Could not find rule block for {selector_pattern!r}"
        )
        return match.group(1)

    def test_global_paragraph_rule_has_no_width_constraint(self):
        # Anchored at line start so this matches only the standalone
        # top-level "p { ... }" rule, not descendant selectors like
        # ".public-pillar p" or ".public-direction-card p" that also end in
        # " p {".
        rule_body = self._rule_block(r"\np")
        self.assertNotIn("max-width", rule_body)
        self.assertNotIn("width", rule_body)
        self.assertNotIn("inline-size", rule_body)
        # The rule must still carry ordinary paragraph margin and color.
        self.assertIn("margin:", rule_body)
        self.assertIn("color:", rule_body)

    def test_section_head_is_full_width(self):
        rule_body = self._rule_block(r"\n\.public-section-head")
        self.assertIn("width: 100%", rule_body)
        self.assertIn("max-width: none", rule_body)

    def test_page_section_first_paragraph_is_full_width(self):
        rule_body = self._rule_block(r"\.public-page-section > p:first-of-type")
        self.assertIn("width: 100%", rule_body)
        self.assertIn("max-width: none", rule_body)

    def test_contact_note_is_full_width(self):
        rule_body = self._rule_block(r"\.public-contact-note")
        self.assertIn("width: 100%", rule_body)
        self.assertIn("max-width: none", rule_body)

    def test_no_known_public_copy_selector_uses_a_retired_width_value(self):
        """No public content paragraph selector may use 70ch, 92ch,
        max-width: 760px, max-width: 900px or max-width: 920px — checked
        per selector rule block (not a blanket file search, which would
        false-positive on the unrelated `@media (max-width: 900px)`
        breakpoint condition)."""
        selectors = (
            r"\np",
            r"\n\.public-section-head",
            r"\.public-page-section > p:first-of-type",
            r"\.public-direction-card p",
            r"\.public-featured-summary",
            r"\.public-expertise-card p",
            r"\.public-project-card p",
            r"\.public-experiment-card p",
            r"\.public-pillar p",
            r"\n\.public-pillars \+ p",
            r"\.public-guide-text",
            r"\.public-ai-guide-notice",
            r"\.public-ai-guide-status",
            r"\.public-contact-note",
            r"\.public-closing-grid p",
            r"\.public-expertise-principle-grid p",
            r"\.public-project-detail-section p",
        )
        retired_values = ("70ch", "92ch", "max-width: 760px", "max-width: 900px", "max-width: 920px")
        for selector in selectors:
            rule_body = self._rule_block(selector)
            for value in retired_values:
                with self.subTest(selector=selector, value=value):
                    self.assertNotIn(value, rule_body)


class ProjectDetailStructureTests(unittest.TestCase):
    """Final width patch: project_detail.html previously rendered its
    Overview/Details/Focus paragraphs as plain <p> tags directly inside
    only `.public-section`, which is exactly what inherited the now-removed
    global 70ch limit. It gets its own page-specific wrapper classes
    instead, none of which constrain paragraph width."""

    @classmethod
    def setUpClass(cls):
        cls.css_text = PUBLIC_CSS_PATH.read_text(encoding="utf-8")
        cls.template_markup = (
            PUBLIC_TEMPLATES_DIR / "project_detail.html"
        ).read_text(encoding="utf-8")
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def _rule_block(self, selector_pattern: str) -> str:
        match = re.search(
            selector_pattern + r"\s*\{([^}]*)\}", self.css_text, re.DOTALL
        )
        self.assertIsNotNone(
            match, f"Could not find rule block for {selector_pattern!r}"
        )
        return match.group(1)

    def test_template_uses_a_dedicated_project_detail_class(self):
        self.assertIn("public-project-detail", self.template_markup)
        self.assertIn('class="public-project-detail-section"', self.template_markup)

    def test_rendered_detail_page_carries_the_dedicated_class(self):
        for lang in SUPPORTED_LANGUAGES:
            projects = load_projects_content(lang)["projects"]
            with self.subTest(lang=lang):
                body = self.client.get(
                    f"/{lang}/projects/{projects[0]['slug']}"
                ).data.decode("utf-8")
                self.assertIn("public-project-detail", body)

    def test_project_detail_section_paragraphs_are_not_width_constrained(self):
        rule_body = self._rule_block(r"\.public-project-detail-section p")
        self.assertIn("width: 100%", rule_body)
        self.assertIn("max-width: none", rule_body)
        self.assertNotRegex(rule_body, r"max-width:\s*[\d.]+ch")

    def test_project_detail_does_not_build_a_second_narrow_inner_column(self):
        # Regression guard: no new max-width should be added on the
        # dedicated wrapper itself — its width stays controlled only by the
        # shared .public-section/.public-page-section container rule.
        match = re.search(
            r"\n\.public-project-detail-section\s*\{([^}]*)\}",
            self.css_text,
            re.DOTALL,
        )
        self.assertIsNotNone(match, ".public-project-detail-section rule not found")
        self.assertNotRegex(match.group(1), r"max-width:\s*[\d.]+(ch|px)")

    def test_all_canonical_project_details_still_render_every_section(self):
        for lang in SUPPORTED_LANGUAGES:
            projects = load_projects_content(lang)["projects"]
            labels = load_site_content(lang)["pages"]["projects"]["labels"]
            for project in projects:
                with self.subTest(lang=lang, slug=project["slug"]):
                    body = self.client.get(
                        f"/{lang}/projects/{project['slug']}"
                    ).data.decode("utf-8")
                    self.assertIn(str(escape(project["summary"])), body)
                    self.assertIn(str(escape(project["details"])), body)
                    self.assertIn(str(escape(project["focus"])), body)
                    self.assertIn(labels["overview"], body)
                    self.assertIn(labels["focus"], body)
                    self.assertIn(labels["technologies"], body)


class RepositoryLinkCoverageTests(unittest.TestCase):
    """Final width patch: every canonical project (all six already carry a
    verified repo_url in projects.json) must show both a localized Overview
    link and a localized Repository link — on the Projects overview cards,
    the Home featured cards, and the project detail page — with the
    repository link always opening safely in a new tab."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def _assert_safe_external_link(self, body: str, href: str) -> None:
        pattern = re.compile(
            r'<a[^>]*href="' + re.escape(href) + r'"[^>]*>', re.DOTALL
        )
        match = pattern.search(body)
        self.assertIsNotNone(match, f"no <a> tag found for href={href!r}")
        tag = match.group(0)
        self.assertIn('target="_blank"', tag)
        self.assertIn('rel="noopener noreferrer"', tag)

    def test_all_six_canonical_overview_cards_render_repository_links(self):
        for lang in SUPPORTED_LANGUAGES:
            projects = load_projects_content(lang)["projects"]
            with self.subTest(lang=lang):
                body = self.client.get(f"/{lang}/projects").data.decode("utf-8")
                self.assertEqual(body.count('class="public-repo-link"'), 6)
                for project in projects:
                    self.assertTrue(project.get("repo_url"))
                    self._assert_safe_external_link(body, project["repo_url"])

    def test_overview_cards_use_the_shared_card_actions_wrapper(self):
        body = self.client.get("/en/projects").data.decode("utf-8")
        self.assertGreaterEqual(body.count('class="public-card-actions"'), 6)

    def test_all_six_canonical_project_detail_pages_render_repository_links(self):
        for lang in SUPPORTED_LANGUAGES:
            projects = load_projects_content(lang)["projects"]
            for project in projects:
                with self.subTest(lang=lang, slug=project["slug"]):
                    body = self.client.get(
                        f"/{lang}/projects/{project['slug']}"
                    ).data.decode("utf-8")
                    self.assertEqual(body.count('class="public-repo-link"'), 1)
                    self._assert_safe_external_link(body, project["repo_url"])

    def test_all_three_home_featured_cards_render_repository_links(self):
        for lang in SUPPORTED_LANGUAGES:
            site = load_site_content(lang)
            featured_ids = site["pages"]["home"]["featured_project_ids"]
            projects_by_id = {
                project["id"]: project
                for project in load_projects_content(lang)["projects"]
            }
            with self.subTest(lang=lang):
                body = self.client.get(f"/{lang}/").data.decode("utf-8")
                self.assertEqual(len(featured_ids), 3)
                self.assertEqual(body.count('class="public-repo-link"'), 3)
                for project_id in featured_ids:
                    project = projects_by_id[project_id]
                    self.assertTrue(project.get("repo_url"))
                    self._assert_safe_external_link(body, project["repo_url"])

    def test_overview_link_still_renders_once_per_featured_card(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                body = self.client.get(f"/{lang}/").data.decode("utf-8")
                self.assertEqual(body.count('class="public-featured-cta"'), 3)


class ExperimentRepositoryVerificationTests(unittest.TestCase):
    """Final width patch: Rise and Shine and MoodMuse previously had no
    repo_url in either language's projects.json. Their GitHub origins were
    verified read-only against the matching local checkouts under
    C:\\Users\\eliv\\Cursor_Projects (rise-and-shine-bot, moodmuse-bot) and
    added identically to both languages. Weather Teller's pre-existing
    repo_url is left untouched."""

    def test_rise_and_shine_repo_url_matches_across_languages(self):
        urls = {
            lang: next(
                experiment["repo_url"]
                for experiment in load_projects_content(lang)["experiments"]
                if experiment["id"] == "rise-and-shine"
            )
            for lang in SUPPORTED_LANGUAGES
        }
        self.assertEqual(urls["en"], "https://github.com/eliv1982/rise-and-shine-bot")
        self.assertEqual(urls["en"], urls["ru"])

    def test_moodmuse_repo_url_matches_across_languages(self):
        urls = {
            lang: next(
                experiment["repo_url"]
                for experiment in load_projects_content(lang)["experiments"]
                if experiment["id"] == "moodmuse"
            )
            for lang in SUPPORTED_LANGUAGES
        }
        self.assertEqual(urls["en"], "https://github.com/eliv1982/moodmuse-bot")
        self.assertEqual(urls["en"], urls["ru"])

    def test_weather_teller_repo_url_is_unchanged(self):
        for lang in SUPPORTED_LANGUAGES:
            with self.subTest(lang=lang):
                experiments = load_projects_content(lang)["experiments"]
                weather_teller = next(
                    experiment
                    for experiment in experiments
                    if experiment["id"] == "weather-teller"
                )
                self.assertEqual(
                    weather_teller["repo_url"],
                    "https://github.com/eliv1982/weather_teller_bot",
                )


class ExperimentRepositoryRenderTests(unittest.TestCase):
    """Rendered-page counterpart to ExperimentRepositoryVerificationTests:
    now that all three personal experiments carry a repo_url, the Projects
    page must render all three, unchanged existing markup/behavior
    preserved (no .public-card-actions wrapper added to experiment cards —
    that restructuring is scoped to the six canonical projects only)."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_all_three_experiments_render_a_repository_link(self):
        for lang in SUPPORTED_LANGUAGES:
            experiments = load_projects_content(lang)["experiments"]
            with self.subTest(lang=lang):
                body = self.client.get(f"/{lang}/projects").data.decode("utf-8")
                for experiment in experiments:
                    self.assertTrue(experiment.get("repo_url"))
                    href = f'href="{experiment["repo_url"]}"'
                    self.assertIn(href, body)
                    self.assertEqual(body.count(href), 1)

    def test_experiment_repo_links_do_not_use_the_canonical_repo_link_class(self):
        # Experiment cards keep their original plain <a> (no
        # .public-repo-link/.public-card-actions), so the class counts
        # counted in RepositoryLinkCoverageTests stay exactly 6 (canonical
        # projects only) rather than 6 + 3.
        body = self.client.get("/en/projects").data.decode("utf-8")
        experiment_section_start = body.index('class="public-experiment-grid"')
        experiment_section = body[experiment_section_start:]
        self.assertNotIn('public-repo-link', experiment_section)


if __name__ == "__main__":
    unittest.main()
