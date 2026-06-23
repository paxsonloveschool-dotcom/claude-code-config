"""Free, no-API caption writer — the $0 alternative to the Claude copywriter.

Turns a clip's transcript into a usable hook + caption + hashtags with pure
Python heuristics: no ANTHROPIC_API_KEY, no network, no cost. Quality is lower
than the Claude writer (``copywriter.generate_caption``), but it keeps the whole
pipeline free and card-free. Returns the SAME ``GeneratedCopy`` shape, so the
orchestrator can swap writers with one flag (``WRITER=free`` vs ``WRITER=claude``).

Heuristics:
- HOOK: the first strong sentence of the transcript (trimmed to ~12 words), or a
  brand default if the transcript is empty.
- CAPTION: the first 1-2 sentences cleaned up, plus a light call-to-action.
- HASHTAGS: the brand's default tags + a few salient keywords from the transcript
  (stop-words removed), lowercased and de-duped.
"""

from __future__ import annotations

import re

from services.write.copywriter import GeneratedCopy

# Tiny stop-word set so keyword picking stays dependency-free.
_STOP = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "for", "with",
    "is", "are", "was", "were", "be", "been", "it", "this", "that", "these",
    "those", "i", "you", "we", "they", "he", "she", "your", "our", "my", "me",
    "at", "as", "so", "if", "then", "than", "too", "very", "just", "can", "will",
    "have", "has", "had", "do", "does", "did", "not", "no", "yes", "get", "got",
    "about", "from", "by", "out", "up", "down", "what", "when", "how", "why",
    "all", "one", "like", "really", "gonna", "wanna", "okay", "ok", "um", "uh",
}

_DEFAULT_CTA = "Follow for more."


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [p.strip() for p in parts if p.strip()]


def _truncate_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).rstrip(",;:") + "…"


_FILLER = {
    "finally", "today", "really", "actually", "basically", "literally",
    "nation", "higher", "purpose", "guys", "everyone", "welcome", "video",
    "thing", "things", "stuff", "going", "doing", "little", "right", "well",
}


def _keywords(text: str, n: int) -> list[str]:
    """Pick a few clean, on-topic keywords. Strict: alphabetic only (drops
    contractions like "what's"), length >= 5, and not a stop/filler word."""
    seen: list[str] = []
    for raw in re.findall(r"[A-Za-z']+", (text or "").lower()):
        w = raw.strip("'")
        if not w.isalpha() or len(w) < 5 or w in _STOP or w in _FILLER or w in seen:
            continue
        seen.append(w)
        if len(seen) >= n:
            break
    return seen


def generate_caption(
    context: dict,
    *,
    default_hashtags: list[str] | None = None,
    cta: str | None = None,
) -> GeneratedCopy:
    """Build ``GeneratedCopy`` from a clip ``context`` with no API call.

    ``context`` keys used: ``transcript`` (preferred), ``title``, ``brand_name``.
    """
    transcript = (context.get("transcript") or context.get("title") or "").strip()
    brand_name = context.get("brand_name") or ""
    sents = _sentences(transcript)

    if sents:
        hook = _truncate_words(sents[0], 12)
        body = " ".join(sents[1:3]).strip() or sents[0]
    else:
        hook = (f"{brand_name}".strip() or "Watch this").strip()
        body = "New clip — take a look."

    cta = cta or _DEFAULT_CTA
    caption = f"{body} {cta}".strip()

    tags: list[str] = []
    for t in (default_hashtags or []):
        t = t.lstrip("#").strip().lower()
        if t and t not in tags:
            tags.append(t)
    # Lean mostly on the brand's curated tags; add at most 2 clean keywords.
    for kw in _keywords(transcript, 2):
        if kw not in tags:
            tags.append(kw)
        if len(tags) >= 10:
            break

    return GeneratedCopy(hook=hook, caption=caption, hashtags=tags[:10])
