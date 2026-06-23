"""Render the bulk review feed — a single static HTML page, no server, no deps.

Clips awaiting approval are shown best-first by ``fire_score`` as a phone-friendly
grid. The owner ticks keepers; a button copies a ``KEEP_IDS`` string to paste into
the pipeline's keep/prune step. **Approval still happens through the existing
workflow** — this page never posts anything, it only helps you choose fast.
"""
from __future__ import annotations

import html


def _score_color(score) -> str:
    if score is None:
        return "#6b7280"          # grey: unscored
    if score >= 70:
        return "#16a34a"          # green: fire
    if score >= 50:
        return "#ca8a04"          # amber: ok
    return "#dc2626"              # red: weak


def sort_items(items: list[dict]) -> list[dict]:
    """Best-first: scored clips by descending fire_score, then unscored, each
    group stable by id so the page is deterministic."""
    def key(it):
        s = it.get("fire_score")
        return (0 if s is not None else 1, -(s or 0), str(it.get("id", "")))
    return sorted(items, key=key)


def render_review_html(items: list[dict], *, title: str = "HP — Bulk Review") -> str:
    """Return a complete HTML document showing ``items`` best-first.

    Each item: ``{id, brand, fire_score?, text?, src, poster?}`` where ``src`` is a
    playable URL or relative path. Pure — no IO — so it's unit-testable.
    """
    ordered = sort_items(items)
    cards = []
    for it in ordered:
        cid = html.escape(str(it.get("id", "")))
        brand = html.escape(str(it.get("brand", "")))
        score = it.get("fire_score")
        score_txt = "—" if score is None else f"{float(score):.0f}"
        color = _score_color(score)
        src = html.escape(str(it.get("src", "")))
        poster = it.get("poster")
        poster_attr = f' poster="{html.escape(str(poster))}"' if poster else ""
        caption = html.escape((it.get("text") or "").strip())[:200]
        cards.append(f"""
      <figure class="card" data-id="{cid}">
        <label class="keep"><input type="checkbox" class="kbox" value="{cid}"> keep</label>
        <span class="badge" style="background:{color}">{score_txt}</span>
        <video src="{src}"{poster_attr} muted loop playsinline preload="metadata"
               controls onmouseover="this.play()" onmouseout="this.pause()"></video>
        <figcaption><b>{brand}</b> · {cid}<br><span class="cap">{caption}</span></figcaption>
      </figure>""")

    body = "\n".join(cards) if cards else '<p class="empty">No clips in review.</p>'
    n = len(ordered)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin:0; background:#0b0f0c; color:#e8efe9;
          font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; }}
  header {{ position:sticky; top:0; z-index:5; background:#0b0f0cdd; backdrop-filter:blur(6px);
            padding:12px 16px; display:flex; gap:12px; align-items:center; border-bottom:1px solid #1c241e; }}
  header h1 {{ font-size:16px; margin:0; }}
  header .count {{ color:#9bb3a2; font-size:13px; }}
  button {{ background:#16a34a; color:#fff; border:0; border-radius:8px; padding:8px 12px;
            font-weight:600; cursor:pointer; }}
  #out {{ font-size:12px; color:#9bb3a2; }}
  .grid {{ display:grid; gap:12px; padding:14px;
           grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); }}
  .card {{ position:relative; margin:0; background:#11181300; border:1px solid #1c241e;
           border-radius:12px; overflow:hidden; }}
  .card video {{ width:100%; aspect-ratio:9/16; object-fit:cover; display:block; background:#000; }}
  .badge {{ position:absolute; top:8px; left:8px; color:#fff; font-weight:700;
            padding:2px 8px; border-radius:999px; font-size:13px; }}
  .keep {{ position:absolute; top:8px; right:8px; background:#000a; padding:3px 7px;
           border-radius:999px; font-size:12px; cursor:pointer; user-select:none; }}
  figcaption {{ padding:8px 10px; font-size:12px; line-height:1.35; }}
  .cap {{ color:#9bb3a2; }}
  .empty {{ padding:40px; text-align:center; color:#9bb3a2; }}
</style></head>
<body>
  <header>
    <h1>🔥 Bulk Review</h1>
    <span class="count">{n} clip(s), best first</span>
    <button onclick="copyKeep()">Copy KEEP_IDS</button>
    <span id="out"></span>
  </header>
  <div class="grid">{body}
  </div>
<script>
  function copyKeep() {{
    const ids = [...document.querySelectorAll('.kbox:checked')].map(b => b.value);
    const s = ids.join(',');
    navigator.clipboard && navigator.clipboard.writeText(s);
    document.getElementById('out').textContent =
      ids.length ? ('copied ' + ids.length + ' id(s)') : 'none selected';
  }}
</script>
</body></html>
"""


if __name__ == "__main__":  # tiny manual preview
    demo = [
        {"id": "hp-a", "brand": "hp", "fire_score": 82, "src": "a.mp4", "text": "fire"},
        {"id": "hp-b", "brand": "hp", "fire_score": 41, "src": "b.mp4", "text": "meh"},
        {"id": "hp-c", "brand": "hp", "src": "c.mp4", "text": "unscored"},
    ]
    print(render_review_html(demo)[:400])
