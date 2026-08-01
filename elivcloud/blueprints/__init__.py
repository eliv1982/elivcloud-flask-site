"""Blueprint package for ElivCloud.

Only the bilingual public site is a blueprint in this slice — admin and the
/chat endpoint remain plain app routes in elivcloud/__init__.py, per the
approved foundation-slice architecture (not split out unless required to
avoid broken imports).
"""
