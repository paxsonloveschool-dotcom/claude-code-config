"""Tests for the Anthropic copywriter (no network, no anthropic install needed).

We inject a fake ``anthropic`` module into ``sys.modules`` so the lazy import
inside ``generate_caption`` resolves to our stub. We then assert the request
payload (model, cached system prompt, user prompt) and that the JSON response is
parsed into ``GeneratedCopy``.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.write import copywriter  # noqa: E402
from services.write.copywriter import GeneratedCopy, generate_caption  # noqa: E402


class _Block:
    def __init__(self, text: str) -> None:
        self.text = text


class _Resp:
    def __init__(self, text: str) -> None:
        self.content = [_Block(text)]


class _FakeMessages:
    def __init__(self, store: dict, reply: str) -> None:
        self._store = store
        self._reply = reply

    def create(self, **kwargs):
        self._store["last_call"] = kwargs
        return _Resp(self._reply)


class _FakeClient:
    def __init__(self, store: dict, reply: str) -> None:
        self.messages = _FakeMessages(store, reply)


def _install_fake_anthropic(store: dict, reply: str):
    mod = types.ModuleType("anthropic")

    def _ctor(*args, **kwargs):
        store["client_args"] = (args, kwargs)
        return _FakeClient(store, reply)

    mod.Anthropic = _ctor
    sys.modules["anthropic"] = mod
    return mod


def test_generate_caption_builds_request_and_parses():
    store: dict = {}
    reply = json.dumps(
        {
            "hook": "You won't believe this",
            "caption": "Here's the wild part.",
            "hashtags": ["#viral", "landscaping", " #diy "],
        }
    )
    _install_fake_anthropic(store, reply)

    context = {
        "transcript": "we regraded the whole yard in one day",
        "title": "Backyard transformation",
        "platform": "tiktok",
        "tone": "energetic",
    }
    result = generate_caption(context)

    # Parsed into the dataclass.
    assert isinstance(result, GeneratedCopy)
    assert result.hook == "You won't believe this"
    assert result.caption == "Here's the wild part."
    # Hashtags normalized: no '#', whitespace trimmed, order preserved.
    assert result.hashtags == ["viral", "landscaping", "diy"]
    assert result.model == "claude-opus-4-8"

    # Request was built correctly.
    call = store["last_call"]
    assert call["model"] == "claude-opus-4-8"
    assert call["max_tokens"] >= 256

    # System prompt is the stable brand prompt with prompt caching applied.
    system = call["system"]
    assert isinstance(system, list) and len(system) == 1
    assert system[0]["text"] == copywriter.BRAND_SYSTEM_PROMPT
    assert system[0]["cache_control"] == {"type": "ephemeral"}

    # User message carries the per-clip context.
    user_content = call["messages"][0]["content"]
    assert call["messages"][0]["role"] == "user"
    assert "tiktok" in user_content
    assert "Backyard transformation" in user_content
    assert "regraded the whole yard" in user_content


def test_parse_tolerates_code_fences():
    store: dict = {}
    reply = '```json\n{"hook":"h","caption":"c","hashtags":["a","b"]}\n```'
    _install_fake_anthropic(store, reply)

    result = generate_caption({"transcript": "x", "platform": "x"})
    assert result.hook == "h"
    assert result.caption == "c"
    assert result.hashtags == ["a", "b"]


def test_build_user_prompt_defaults():
    prompt = copywriter._build_user_prompt({})
    assert "Platform: tiktok" in prompt
    assert "Tone: energetic" in prompt


def _run():
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  PASS {name}")
            passed += 1
    print(f"\n{passed} tests passed.")


if __name__ == "__main__":
    _run()
