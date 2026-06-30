"""Bulk review feed: a static, best-first page of clips awaiting approval.

Phase 4 of the bulk pipeline. ``feed.render_review_html`` is a pure function
(easy to unit-test); the IO driver that loads the queue and writes the page
lives in ``automation/video_pipeline.py`` (``build_review_feed``).
"""
