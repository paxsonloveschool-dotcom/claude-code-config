"""AI-generate hooks / captions / hashtags for a clip via the Anthropic SDK.

Given context about a clip (its transcript, title, platform, etc.), generate a
scroll-stopping hook, a platform-appropriate caption, and a set of hashtags.

The ``anthropic`` package is imported lazily *inside* ``generate_caption`` so the
module (and the wider package) imports cleanly without the SDK installed.

Reference call shape (model ``claude-opus-4-8``):

    import anthropic
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    resp = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1024,
        system=[{"type": "text", "text": BRAND_SYSTEM_PROMPT,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": _build_user_prompt(context)}],
    )
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")

# Stable brand/system prompt. Kept module-level and constant so prompt caching
# (cache_control) gives a real hit across calls.
BRAND_SYSTEM_PROMPT = """\
You are a world-class short-form social copywriter for an in-house content team.
You write hooks, captions, and hashtags for vertical video clips (TikTok, Reels,
Shorts, etc.). Your copy is punchy, native to each platform, and engineered to
stop the scroll in the first second.

Rules:
- The HOOK is one short line (max ~12 words) that creates curiosity or tension.
  It is what appears on-screen and as the first line of the caption.
- The CAPTION is the post body: 1-3 short sentences, conversational, with a
  light call-to-action. Do NOT restate the hook verbatim. No markdown.
- HASHTAGS: 4-10 relevant, lowercase, specific (mix broad + niche). Return them
  WITHOUT the leading '#'. No spaces inside a tag.
- Match the requested platform and tone. Never invent facts not in the context.
- Respond with ONLY a single JSON object, no prose, no code fences.

Output JSON schema (exactly these keys):
{"hook": str, "caption": str, "hashtags": [str, ...]}
"""


@dataclass
class GeneratedCopy:
    """AI-generated copy for one clip.

    Attributes:
        hook: Short scroll-stopping opening line / on-screen hook.
        caption: Platform caption body.
        hashtags: Hashtags (without duplicating the '#' if already present).
        model: The Claude model id used to generate this copy.
    """

    hook: str
    caption: str
    hashtags: list[str] = field(default_factory=list)
    model: str = MODEL


def _build_user_prompt(context: dict) -> str:
    """Render the per-clip context into the user-turn instruction string."""
    transcript = (context.get("transcript") or "").strip()
    title = (context.get("title") or "").strip()
    platform = (context.get("platform") or "tiktok").strip()
    tone = (context.get("tone") or "energetic").strip()

    lines = [
        f"Platform: {platform}",
        f"Tone: {tone}",
    ]
    if title:
        lines.append(f"Title: {title}")
    if transcript:
        lines.append("Clip transcript:\n" + transcript)
    lines.append(
        "\nWrite the hook, caption, and hashtags for THIS clip. "
        "Return only the JSON object."
    )
    return "\n".join(lines)


def _normalize_hashtags(raw) -> list[str]:
    """Coerce model hashtag output into a clean list (no leading '#')."""
    if isinstance(raw, str):
        raw = raw.replace(",", " ").split()
    tags: list[str] = []
    for t in raw or []:
        t = str(t).strip().lstrip("#").strip()
        if t:
            tags.append(t)
    return tags


def _extract_text(resp) -> str:
    """Pull the concatenated text from an Anthropic Messages response."""
    parts: list[str] = []
    for block in getattr(resp, "content", []) or []:
        text = getattr(block, "text", None)
        if text is None and isinstance(block, dict):
            text = block.get("text")
        if text:
            parts.append(text)
    return "".join(parts).strip()


def _parse_json_object(text: str) -> dict:
    """Parse a JSON *object* from model text, tolerating code fences / prose.

    Raises ``ValueError`` with the offending text when no JSON object can be
    recovered (empty reply, a JSON array/scalar, or unparseable prose) — rather
    than letting a later ``.get`` blow up with an obscure ``AttributeError``.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("Empty response from the model (no copy generated).")

    candidate = text
    if candidate.startswith("```"):
        # Strip ```json ... ``` (or plain ```) fences, keeping the inner body.
        if candidate.count("```") >= 2:
            candidate = candidate.split("```", 2)[1]
        else:
            candidate = candidate[3:]
        candidate = candidate.lstrip()
        if candidate.lower().startswith("json"):
            candidate = candidate[4:]
        candidate = candidate.strip()

    parsed = None
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        # Defensive: extract the first {...} object embedded in prose.
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(candidate[start : end + 1])
            except json.JSONDecodeError:
                parsed = None

    if not isinstance(parsed, dict):
        raise ValueError(
            "Could not parse a JSON object from the model response: "
            f"{text[:200]!r}"
        )
    return parsed


def generate_caption(context: dict) -> GeneratedCopy:
    """Generate a hook, caption, and hashtags for a clip.

    Args:
        context: Free-form clip context, e.g. {"transcript": ..., "title": ...,
            "platform": "tiktok", "tone": "energetic"}.

    Returns:
        A ``GeneratedCopy`` with hook + caption + hashtags.
    """
    import anthropic  # lazy: keep module import dep-free

    model = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    resp = client.messages.create(
        model=model,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": BRAND_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": _build_user_prompt(context)}],
    )

    data = _parse_json_object(_extract_text(resp))
    return GeneratedCopy(
        hook=str(data.get("hook", "")).strip(),
        caption=str(data.get("caption", "")).strip(),
        hashtags=_normalize_hashtags(data.get("hashtags")),
        model=model,
    )
