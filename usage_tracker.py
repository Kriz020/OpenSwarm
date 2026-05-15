"""DeepSeek usage tracker via LiteLLM callback.

Writes cumulative session stats to ~/.deepseek_usage.json after each call.
"""

import json
import time
from pathlib import Path

import litellm

USAGE_FILE = Path.home() / ".deepseek_usage.json"

# DeepSeek V4 Pro pricing (USD per 1M tokens)
_PRICE = {
    "input":  0.50,
    "output": 2.19,
}


def _load() -> dict:
    if USAGE_FILE.exists():
        try:
            return json.loads(USAGE_FILE.read_text())
        except Exception:
            pass
    return {"session_start": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
            "cost_usd": 0.0, "calls": 0}


def _save(data: dict) -> None:
    USAGE_FILE.write_text(json.dumps(data, indent=2))


def _on_success(kwargs, response, start_time, end_time, *args, **extra):
    try:
        usage = response.usage
        if not usage:
            return
        data = _load()
        inp = getattr(usage, "prompt_tokens", 0) or 0
        out = getattr(usage, "completion_tokens", 0) or 0
        cost = (inp / 1_000_000 * _PRICE["input"]) + (out / 1_000_000 * _PRICE["output"])
        data["input_tokens"]  += inp
        data["output_tokens"] += out
        data["total_tokens"]  += inp + out
        data["cost_usd"]      += cost
        data["calls"]         += 1
        data["last_updated"]   = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _save(data)
    except Exception:
        pass


def reset_session():
    """Call this to start a fresh session counter."""
    _save({"session_start": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
           "cost_usd": 0.0, "calls": 0})


def register():
    litellm.success_callback = getattr(litellm, "success_callback", []) or []
    if _on_success not in litellm.success_callback:
        litellm.success_callback.append(_on_success)
    reset_session()
