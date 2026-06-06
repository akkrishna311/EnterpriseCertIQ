"""
LLM response cache — SHA-256 keyed, file-backed.

A cache key is the SHA-256 of the canonicalised request (model + messages +
tools + temperature + max_tokens). On a hit the model call is skipped entirely,
which:
  - cuts Azure/Foundry token cost on repeated identical inputs,
  - makes the demo path instant and deterministic (judge re-runs the same
    persona → 0 ms, identical output),
  - removes a network dependency for cached runs.

The cache stores the *serialised chat completion* (choices/message/usage) so it
can be rehydrated into the same object shape BaseAgent already consumes.

Thread/async note: the workflow runs agents sequentially per request, and writes
are last-write-wins on a small JSON file — fine for this single-node app. Swap the
backend for Cosmos/Redis in production without changing the public API.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
from pathlib import Path
from typing import Any, Optional

from config.settings import get_settings

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_STATS = {"hits": 0, "misses": 0, "writes": 0}


def _cache_path() -> Path:
    s = get_settings()
    return Path(s.store_dir) / "llm_response_cache.json"


def make_key(model: str, messages: list[dict], tools: Optional[list] = None,
             temperature: float = 0.0, max_tokens: int = 0) -> str:
    """Deterministic SHA-256 over the request shape."""
    payload = json.dumps(
        {"model": model, "messages": messages, "tools": tools or [],
         "temperature": temperature, "max_tokens": max_tokens},
        sort_keys=True, ensure_ascii=False, default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _read() -> dict:
    p = _cache_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write(data: dict) -> None:
    try:
        _cache_path().write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("LLM cache write failed: %s", e)


def get(key: str) -> Optional[dict]:
    """Return the cached completion dict for `key`, or None. Updates hit/miss stats."""
    if not get_settings().enable_llm_cache:
        return None
    with _LOCK:
        data = _read()
        entry = data.get(key)
        if entry is not None:
            _STATS["hits"] += 1
            entry["hit_count"] = entry.get("hit_count", 0) + 1
            data[key] = entry
            _write(data)
            return entry["response"]
        _STATS["misses"] += 1
        return None


def put(key: str, response: dict) -> None:
    """Store a completion dict under `key`, evicting oldest entries past the cap."""
    s = get_settings()
    if not s.enable_llm_cache:
        return
    with _LOCK:
        data = _read()
        data[key] = {"response": response, "hit_count": 0}
        # Simple FIFO eviction to bound the file size.
        if len(data) > s.llm_cache_max_entries:
            for stale_key in list(data.keys())[: len(data) - s.llm_cache_max_entries]:
                data.pop(stale_key, None)
        _write(data)
        _STATS["writes"] += 1


def stats() -> dict:
    """Live hit/miss/write counters + persisted entry count (for the dashboard)."""
    total = _STATS["hits"] + _STATS["misses"]
    with _LOCK:
        entries = len(_read())
    return {
        **_STATS,
        "entries": entries,
        "hit_rate": round(_STATS["hits"] / total, 3) if total else 0.0,
        "enabled": get_settings().enable_llm_cache,
    }


def clear() -> None:
    with _LOCK:
        _write({})
        _STATS.update(hits=0, misses=0, writes=0)


def rehydrate_completion(cached: dict) -> Any:
    """Rebuild a minimal object matching the chat-completion shape BaseAgent reads:
    `resp.choices[0].message.{content,tool_calls}` and `resp.usage.*`."""
    from types import SimpleNamespace

    tool_calls = [
        SimpleNamespace(
            id=tc["id"],
            type=tc.get("type", "function"),
            function=SimpleNamespace(
                name=tc["function"]["name"],
                arguments=tc["function"]["arguments"],
            ),
        )
        for tc in cached.get("tool_calls", [])
    ] or None
    message = SimpleNamespace(content=cached.get("content"), tool_calls=tool_calls)
    usage = SimpleNamespace(
        prompt_tokens=cached.get("usage", {}).get("prompt_tokens", 0),
        completion_tokens=cached.get("usage", {}).get("completion_tokens", 0),
    )
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage,
                           from_cache=True)


def serialize_completion(response: Any) -> dict:
    """Serialise an OpenAI/Foundry chat completion into a cache-safe dict.

    Captures only what BaseAgent reads back: the first choice's message
    (content + tool_calls) and usage. Returns None-free, JSON-safe data.
    """
    try:
        choice = response.choices[0]
        msg = choice.message
        tool_calls = []
        for tc in (getattr(msg, "tool_calls", None) or []):
            tool_calls.append({
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            })
        usage = getattr(response, "usage", None)
        return {
            "content": getattr(msg, "content", None),
            "tool_calls": tool_calls,
            "usage": {
                "prompt_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
                "completion_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
            },
        }
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("Could not serialise completion for cache: %s", e)
        return {}
