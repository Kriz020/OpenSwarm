"""Fix: preserve reasoning_content across DeepSeek conversation turns.

Root cause (SDK bug in chatcmpl_converter.py):
  `flush_assistant_message()` clears `pending_reasoning_content` when called
  with no current assistant message — which is exactly what happens when a
  plain-text response follows a reasoning item. Result: the outgoing message
  dict is missing `reasoning_content`, and DeepSeek rejects the next request
  with "reasoning_content must be passed back to the API".

Fix strategy:
  1. Wrap `litellm.completion / acompletion` to cache `reasoning_content`
     keyed by a sha256 of the response's text content.
  2. Wrap `Converter.items_to_messages` to post-process the result: any
     assistant message that is missing `reasoning_content` but whose content
     is in the cache gets the value reinjected before the call goes to DeepSeek.

This preserves the full chain-of-thought across all turns, including plain-text
responses (not just tool-call turns that the SDK already handles correctly).
"""

import hashlib
import litellm
from agents.models.chatcmpl_converter import Converter

# ── Cache ─────────────────────────────────────────────────────────────────────

_reasoning_cache: dict[str, str] = {}


def _key(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def _cache_from_response(response) -> None:
    """Store reasoning_content from a DeepSeek response for future turns."""
    try:
        for choice in response.choices:
            msg = getattr(choice, "message", None)
            if msg is None:
                continue
            rc = getattr(msg, "reasoning_content", None)
            content = getattr(msg, "content", None)
            if rc and content and isinstance(content, str):
                _reasoning_cache[_key(content)] = rc
    except Exception:
        pass


# ── Wrap litellm to cache reasoning_content ───────────────────────────────────

_orig_completion = litellm.completion
_orig_acompletion = litellm.acompletion


def _patched_completion(*args, **kwargs):
    response = _orig_completion(*args, **kwargs)
    _cache_from_response(response)
    return response


async def _patched_acompletion(*args, **kwargs):
    response = await _orig_acompletion(*args, **kwargs)
    _cache_from_response(response)
    return response


# ── Fix Converter.items_to_messages output ────────────────────────────────────

_orig_items_to_messages = Converter.items_to_messages  # already bound classmethod


@classmethod  # type: ignore[misc]
def _fixed_items_to_messages(cls, *args, **kwargs):
    result: list = _orig_items_to_messages(*args, **kwargs)

    for msg in result:
        if not (isinstance(msg, dict) and msg.get("role") == "assistant"):
            continue
        if "reasoning_content" in msg:
            continue  # SDK already handled it (tool-call case)
        content = msg.get("content")
        if not (isinstance(content, str) and content):
            continue
        cached = _reasoning_cache.get(_key(content))
        if cached:
            msg["reasoning_content"] = cached

    return result


# ── Apply all patches ─────────────────────────────────────────────────────────

def apply_deepseek_reasoning_patch():
    litellm.completion = _patched_completion
    litellm.acompletion = _patched_acompletion
    Converter.items_to_messages = _fixed_items_to_messages
