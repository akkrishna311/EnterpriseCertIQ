"""
Azure AI Content Safety guardrail.

When `AZURE_CONTENT_SAFETY_ENDPOINT` + `AZURE_CONTENT_SAFETY_KEY` are set, free-text
agent output is screened by the live Content Safety `text:analyze` API across the
Hate / SelfHarm / Sexual / Violence categories. Any category at severity >=
`AZURE_CONTENT_SAFETY_THRESHOLD` → BLOCK.

When unconfigured (local/demo), it falls back to a fast regex guard so the same
code path always returns a verdict — no network dependency required offline.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from config.settings import get_settings

logger = logging.getLogger(__name__)

_CATEGORIES = ["Hate", "SelfHarm", "Sexual", "Violence"]

# Regex fallback — conservative harmful-content + jailbreak markers.
_REGEX_BLOCKLIST = [
    re.compile(r"\b(kill yourself|self[-\s]?harm|suicide)\b", re.IGNORECASE),
    re.compile(r"\b(make a bomb|build a weapon|how to hack)\b", re.IGNORECASE),
    re.compile(r"\bignore\s+(?:all\s+)?(?:previous\s+)?instructions\b", re.IGNORECASE),
    re.compile(r"\b(jailbreak|do anything now)\b", re.IGNORECASE),
]


def content_safety_mode() -> str:
    """'azure' when the live API is configured, else 'regex'."""
    s = get_settings()
    return "azure" if (s.azure_content_safety_endpoint and s.azure_content_safety_key) else "regex"


def _regex_verdict(text: str) -> tuple[bool, str, dict]:
    for pattern in _REGEX_BLOCKLIST:
        if pattern.search(text):
            return False, f"regex blocklist matched: {pattern.pattern}", {"mode": "regex"}
    return True, "", {"mode": "regex"}


def _azure_verdict(text: str) -> tuple[bool, str, dict]:
    """Live Content Safety call. Falls back to regex on any error."""
    import httpx

    s = get_settings()
    url = f"{s.azure_content_safety_endpoint.rstrip('/')}/contentsafety/text:analyze"
    try:
        with httpx.Client(timeout=5) as client:
            r = client.post(
                url,
                params={"api-version": "2024-09-01"},
                headers={"Ocp-Apim-Subscription-Key": s.azure_content_safety_key},
                json={"text": text[:10000], "categories": _CATEGORIES,
                      "outputType": "FourSeverityLevels"},
            )
            r.raise_for_status()
            analysis = r.json().get("categoriesAnalysis", [])
        severities = {a.get("category"): a.get("severity", 0) for a in analysis}
        worst = max(severities.values(), default=0)
        if worst >= s.azure_content_safety_threshold:
            flagged = {c: v for c, v in severities.items() if v >= s.azure_content_safety_threshold}
            return False, f"Azure Content Safety flagged: {flagged}", {"mode": "azure", "severities": severities}
        return True, "", {"mode": "azure", "severities": severities}
    except Exception as e:
        logger.warning("Content Safety API failed, falling back to regex: %s", e)
        ok, reason, details = _regex_verdict(text)
        details["mode"] = "azure_fallback_regex"
        details["error"] = str(e)
        return ok, reason, details


def analyze_text(text: str) -> tuple[bool, str, dict]:
    """Return (is_safe, reason, details). Uses the live API when configured."""
    if not text or not text.strip():
        return True, "", {"mode": content_safety_mode()}
    if content_safety_mode() == "azure":
        return _azure_verdict(text)
    return _regex_verdict(text)
