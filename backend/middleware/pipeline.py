"""
Middleware pipeline — applied to every agent result before it leaves the system.

Guards (in order):
  1. pii_redaction   — strip synthetic IDs that look like real names
  2. citation_gate   — drop uncited assertions
  3. content_safety  — Azure AI Content Safety (live) or regex fallback
  4. safety          — flag/replace harmful output (legacy keyword guard)
  5. fairness        — scan for bias patterns in generated content
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from backend.middleware.content_safety import analyze_text, content_safety_mode

logger = logging.getLogger(__name__)

# ── PII patterns (protect against accidental real-name leakage) ────────────
# Email + phone are redacted unconditionally (no false positives on synthetic data).
_PII_PATTERNS = [
    (re.compile(r"\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b"), "[REDACTED-EMAIL]"),
    (re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[REDACTED-PHONE]"),
]

# A naive "TitleCase TitleCase" name regex over-matches domain vocabulary
# (e.g. "Cloud Engineer", "Azure Functions", "Study Plan"), which corrupts
# structured agent output. We only redact a capitalised bigram when NEITHER
# token is part of the certification / domain vocabulary below. This keeps the
# defence-in-depth PII guard while preserving legitimate technical content.
_NAME_BIGRAM = re.compile(r"\b([A-Z][a-z]+) ([A-Z][a-z]+)\b")
_DOMAIN_VOCAB = {
    "azure", "cloud", "data", "engineer", "devops", "architect", "developer",
    "microsoft", "learn", "study", "plan", "functions", "function", "storage",
    "compute", "security", "monitoring", "networking", "deployment", "develop",
    "solutions", "solution", "service", "services", "container", "containers",
    "app", "apps", "database", "databases", "pipeline", "pipelines", "integration",
    "design", "implement", "manage", "configure", "general", "foundations",
    "readiness", "assessment", "certification", "cert", "exam", "domain", "domains",
    "team", "learner", "manager", "insights", "engagement", "curator", "retrospective",
    "option", "source", "guide", "report", "morning", "afternoon", "evening",
    "synthetic", "easy", "medium", "hard", "high", "low", "pass", "fail",
}


def _redact_names(text: str) -> str:
    def _sub(m: "re.Match") -> str:
        first, second = m.group(1), m.group(2)
        if first.lower() in _DOMAIN_VOCAB or second.lower() in _DOMAIN_VOCAB:
            return m.group(0)  # legitimate domain term — leave untouched
        return "[REDACTED-NAME]"
    return _NAME_BIGRAM.sub(_sub, text)

# ── Bias patterns to flag ──────────────────────────────────────────────────
_BIAS_PATTERNS = [
    re.compile(r"\b(he|him|his)\b", re.IGNORECASE),     # gendered pronouns without context
    re.compile(r"\bjunior\b.*\bshould\b", re.IGNORECASE),
    re.compile(r"\bsenior\b.*\bwill\b", re.IGNORECASE),
]

# ── Safety keywords (very conservative for demo) ──────────────────────────
_UNSAFE_PATTERNS = [
    re.compile(r"\b(hack|exploit|bypass|jailbreak)\b", re.IGNORECASE),
]


def redact_pii(text: str) -> str:
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    text = _redact_names(text)
    return text


def drop_uncited_claims(text: str, agent_name: str = "") -> str:
    """
    Citation gate: for assessment/curator agents, warn if no citation markers present.
    Does not rewrite — flags a warning so the trace captures it.
    """
    if agent_name in ("curator", "assessment", "readiness_critic"):
        if "citation" not in text.lower() and "[source:" not in text.lower():
            logger.warning("[citation-gate] Agent '%s' returned output with no citation markers", agent_name)
    return text  # pass-through; flagging only


def check_safety(text: str) -> tuple[bool, str]:
    for pattern in _UNSAFE_PATTERNS:
        if pattern.search(text):
            logger.warning("[safety] Unsafe pattern detected in output")
            return False, "[Content flagged by safety middleware — output withheld]"
    return True, text


def bias_audit(text: str, agent_name: str = "") -> list[str]:
    findings: list[str] = []
    for pattern in _BIAS_PATTERNS:
        if pattern.search(text):
            findings.append(f"Potential bias pattern matched: {pattern.pattern}")
    if findings:
        logger.warning("[bias-audit] %s in output from '%s'", findings, agent_name)
    return findings


def apply_pipeline(content: str, agent_name: str = "") -> tuple[str, list[str]]:
    """
    Run the full middleware pipeline.
    Returns (processed_content, list_of_warnings).
    """
    warnings: list[str] = []

    content = redact_pii(content)
    content = drop_uncited_claims(content, agent_name)

    # Azure AI Content Safety (live API when configured, regex fallback otherwise).
    cs_safe, cs_reason, cs_details = analyze_text(content)
    if not cs_safe:
        logger.warning("[content-safety:%s] %s", cs_details.get("mode"), cs_reason)
        warnings.append(f"content_safety_block:{cs_details.get('mode')}")
        content = "[Content withheld by Azure AI Content Safety guardrail]"

    safe, content = check_safety(content)
    if not safe:
        warnings.append("safety_flag")

    bias_findings = bias_audit(content, agent_name)
    warnings.extend(bias_findings)

    return content, warnings
