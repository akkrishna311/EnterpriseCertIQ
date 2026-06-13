"""
Unit tests for EnterpriseCertIQ core behaviour.

Fast, model-free tests covering the pieces most likely to regress:
  - PII middleware (must preserve domain vocabulary, redact real names/emails)
  - structured-output extraction (reasoning-model <think> stripping)
  - assessment generation + server-side scoring (answer key not always index 0)
  - readiness forecast honesty (insufficient evidence)
  - workflow guard helpers

Run with:  pytest -q
"""
from __future__ import annotations

import json

import pytest

from backend.middleware.pipeline import redact_pii, apply_pipeline
from backend.core.agent import BaseAgent
from backend.core.workflow import (
    _has_red_objection,
    _readiness_from_forecast,
)
from backend.mcp_server.server import (
    generate_assessment,
    compute_readiness_forecast,
    AssessmentInput,
    ForecastInput,
)


# ── PII middleware ──────────────────────────────────────────────────────────

def test_pii_preserves_domain_terms():
    text = "The Cloud Engineer studies Azure Functions and Data Storage for the Study Plan."
    out = redact_pii(text)
    assert "Cloud Engineer" in out
    assert "Azure Functions" in out
    assert "[REDACTED-NAME]" not in out


def test_pii_redacts_email_and_phone():
    out = redact_pii("Reach me at jane@example.com or 555-123-4567")
    assert "[REDACTED-EMAIL]" in out
    assert "[REDACTED-PHONE]" in out


def test_pipeline_returns_warnings_list():
    _, warnings = apply_pipeline("Some grounded text with a citation.", "curator")
    assert isinstance(warnings, list)


# ── Structured-output extraction (reasoning models) ──────────────────────────

def test_extract_json_strips_think_block():
    agent = BaseAgent(name="t", instructions="")
    content = '<think>Let me reason about this carefully...</think>\n{"objections": []}'
    payload = agent._extract_json_payload(content)
    assert payload == {"objections": []}


def test_extract_json_from_fenced_block():
    agent = BaseAgent(name="t", instructions="")
    content = "Here is the result:\n```json\n{\"a\": 1}\n```"
    assert agent._extract_json_payload(content) == {"a": 1}


def test_extract_json_balanced_fallback():
    agent = BaseAgent(name="t", instructions="")
    content = "prose [1, 2, 3] trailing"
    assert agent._extract_json_payload(content) == [1, 2, 3]


# ── Workflow guard helpers ───────────────────────────────────────────────────

def test_has_red_objection_true():
    assert _has_red_objection({"objections": [{"severity": "red"}]}) is True


def test_has_red_objection_false():
    assert _has_red_objection({"objections": [{"severity": "amber"}]}) is False



# ── Assessment generation + scoring ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_assessment_correct_index_not_always_zero():
    a = await generate_assessment.fn(AssessmentInput(
        learner_id="L-1004", cert_id="AZ-204", question_count=12,
    ))
    idxs = {q["correct_index"] for q in a["questions"]}
    # With shuffling, the correct answer should not be pinned to a single index.
    assert idxs != {0}
    assert all(0 <= i <= 3 for i in idxs)


@pytest.mark.asyncio
async def test_assessment_questions_have_citations():
    a = await generate_assessment.fn(AssessmentInput(
        learner_id="L-1004", cert_id="AZ-204", question_count=6,
    ))
    assert a["questions"], "expected questions"
    assert all(q.get("citations") for q in a["questions"])


@pytest.mark.asyncio
async def test_assessment_questions_grounded_in_excerpt():
    """Questions should embed the approved-source excerpt, not just a template."""
    a = await generate_assessment.fn(AssessmentInput(
        learner_id="L-1004", cert_id="AZ-204", question_count=6,
    ))
    grounded = [q for q in a["questions"] if "Approved source" in q["question_text"]]
    assert grounded, "expected at least one question grounded in a retrieved excerpt"


@pytest.mark.asyncio
async def test_assessment_difficulty_filter():
    a = await generate_assessment.fn(AssessmentInput(
        learner_id="L-1004", cert_id="AZ-204", question_count=6, difficulty="Hard",
    ))
    assert all(q["difficulty"] == "Hard" for q in a["questions"])


# ── Readiness decision (Assessment Agent loop-back control flow) ─────────────

def test_readiness_decision_ready_advances():
    d = _readiness_from_forecast({"estimated_exam_score": 780, "pass_threshold": 700})
    assert d["recommendation"] == "advance" and d["verdict"] == "ready"


def test_readiness_decision_below_threshold_remediates():
    d = _readiness_from_forecast({"estimated_exam_score": 600, "pass_threshold": 700,
                                  "weakest_topic": "data"})
    assert d["recommendation"] == "remediate" and d["verdict"] == "not_ready"
    assert d["weakest_topic"] == "data"


def test_readiness_decision_insufficient_evidence():
    d = _readiness_from_forecast({"insufficient_evidence": True})
    assert d["recommendation"] == "gather_evidence"


# ── Readiness forecast honesty ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_forecast_insufficient_evidence():
    f = await compute_readiness_forecast.fn(ForecastInput(
        learner_id="L-1007", cert_id="AZ-204", plan_id="x", evidence_json="{}",
    ))
    assert f["insufficient_evidence"] is True


@pytest.mark.asyncio
async def test_forecast_with_evidence_has_confidence_interval():
    evidence = {"compute": 0.8, "storage": 0.75, "security": 0.7, "monitoring": 0.85}
    f = await compute_readiness_forecast.fn(ForecastInput(
        learner_id="L-1004", cert_id="AZ-204", plan_id="x",
        evidence_json=json.dumps(evidence),
    ))
    assert f["insufficient_evidence"] is False
    assert f["confidence_interval_lower"] <= f["pass_probability"] <= f["confidence_interval_upper"]
