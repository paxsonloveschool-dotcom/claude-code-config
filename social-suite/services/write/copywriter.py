"""AI-generate hooks / captions / hashtags for a clip via the Anthropic SDK.

Given context about a clip (its transcript, title, platform, etc.), generate a
scroll-stopping hook, a platform-appropriate caption, and a set of hashtags.

TODO(impl): fill in with the Anthropic Python SDK (`anthropic`).
    - Model: claude-opus-4-8 (do not downgrade unless explicitly required).
    - Use adaptive thinking: thinking={"type": "adaptive"}.
    - Prefer structured outputs (output_config.format with a json_schema, or
      client.messages.parse with a Pydantic model) so hook/caption/hashtags come
      back already separated — assistant prefill is NOT supported on this model.
    - Read ANTHROPIC_API_KEY / ANTHROPIC_MODEL from the environment.

Reference shape of a real call (left commented so the skeleton imports without
the anthropic package installed):

    import anthropic
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    resp = client.messages.create(
        model=os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8"),
        max_tokens=1024,
        thinking={"type": "adaptive"},
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": _build_prompt(context)}],
    )
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")


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


def generate_caption(context: dict) -> GeneratedCopy:
    """Generate a hook, caption, and hashtags for a clip.

    Args:
        context: Free-form clip context, e.g. {"transcript": ..., "title": ...,
            "platform": "tiktok", "tone": "energetic"}.

    Returns:
        A ``GeneratedCopy`` with hook + caption + hashtags.

    TODO(impl): call the Anthropic SDK (model=claude-opus-4-8, adaptive thinking,
        structured outputs). See module docstring for the reference call.
    """
    raise NotImplementedError(
        "Call the Anthropic SDK (claude-opus-4-8) to generate hook/caption/hashtags."
    )
