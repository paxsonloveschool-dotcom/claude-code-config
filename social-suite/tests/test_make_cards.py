"""Tests for automation/make_cards.py. Renderer is faked — no Pillow needed."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from automation import make_cards  # noqa: E402

_QUEUE = [
    {"id": "hp-001", "brand": "hp", "text": "spring", "media_url": None,
     "platforms": ["facebook"], "schedule": None, "status": "sent"},
    {"id": "hp-002", "brand": "hp", "text": "before/after", "media_url": "https://x/y.jpg",
     "platforms": ["facebook"], "schedule": None, "status": "paused"},
    {"id": "restore-001", "brand": "restore", "text": "water damage", "media_url": None,
     "platforms": ["facebook"], "schedule": None, "status": "paused"},
]


def test_plan_skips_posts_that_already_have_media():
    actions = make_cards.plan([dict(p) for p in _QUEUE])
    ids = {a["id"] for a in actions}
    assert ids == {"hp-001", "restore-001"}  # hp-002 has media → skipped


def test_plan_filters_by_brand():
    actions = make_cards.plan([dict(p) for p in _QUEUE], brand="restore")
    assert [a["id"] for a in actions] == ["restore-001"]


def test_raw_url_shape():
    url = make_cards.raw_url("hp-007", repo="owner/repo", branch="main")
    assert url == ("https://raw.githubusercontent.com/owner/repo/main/"
                   "social-suite/content/cards/hp-007.png")


def test_apply_sets_media_url_adds_instagram_and_keeps_status(tmp_path, monkeypatch):
    monkeypatch.setattr(make_cards, "CARDS_DIR", str(tmp_path / "cards"))
    queue = [dict(p) for p in _QUEUE]
    rendered = []

    def fake_render(text, out_path, brand_name=None, theme=None):
        rendered.append((out_path, brand_name, theme))
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(b"PNG")
        return out_path

    actions = make_cards.plan(queue, brand="hp", add_instagram=True)
    n = make_cards.apply(queue, actions, render_fn=fake_render)

    assert n == 1
    hp1 = next(p for p in queue if p["id"] == "hp-001")
    # media_url now points at the committed card; instagram added; status intact
    assert hp1["media_url"].endswith("social-suite/content/cards/hp-001.png")
    assert "instagram" in hp1["platforms"] and "facebook" in hp1["platforms"]
    assert hp1["status"] == "sent"  # NEVER changed → cannot cause a post
    # used HP's brand styling
    assert rendered[0][1] == "HP Landscaping" and rendered[0][2] == "green"


def test_apply_without_add_instagram_leaves_platforms(tmp_path):
    queue = [dict(p) for p in _QUEUE]
    make_cards.CARDS_DIR = str(tmp_path / "cards")

    def fake_render(text, out_path, brand_name=None, theme=None):
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(b"PNG")
        return out_path

    actions = make_cards.plan(queue, brand="restore", add_instagram=False)
    make_cards.apply(queue, actions, render_fn=fake_render)
    r1 = next(p for p in queue if p["id"] == "restore-001")
    assert r1["media_url"]  # got a card
    assert r1["platforms"] == ["facebook"]  # instagram NOT added


def _run():
    import tempfile

    class _MP:
        def setattr(self, obj, name, val):
            setattr(obj, name, val)

    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            import inspect

            params = inspect.signature(fn).parameters
            kwargs = {}
            with tempfile.TemporaryDirectory() as d:
                if "tmp_path" in params:
                    kwargs["tmp_path"] = Path(d)
                if "monkeypatch" in params:
                    kwargs["monkeypatch"] = _MP()
                fn(**kwargs)
            print(f"  PASS {name}")
            passed += 1
    print(f"\n{passed} tests passed.")


if __name__ == "__main__":
    _run()
