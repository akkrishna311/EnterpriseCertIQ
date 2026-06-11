"""Rubric-based agent-quality eval tests (deterministic, zero-credential).

Good outputs pass the 0.8 threshold; deliberately broken outputs fail the specific check.
"""
import json

import pytest

from backend.evals.agent_rubrics import evaluate_agent_output, batch_evaluate
from backend.mcp_server.server import (
    generate_study_plan, StudyPlanInput,
    compute_readiness_forecast, ForecastInput,
    compute_domain_mastery, DomainMasteryInput,
)


# ── plan_generator (uses the real deterministic MCP tool output) ─────────────
@pytest.mark.asyncio
async def test_plan_rubric_passes_on_real_tool_output():
    plan = await generate_study_plan.fn(StudyPlanInput(
        learner_id="L-1004", cert_id="AZ-204",
        curated_topics_json=json.dumps([
            {"title": "Azure Functions", "domain": "Compute", "hours": 4},
            {"title": "Blob Storage", "domain": "Storage", "hours": 3},
        ]),
        available_hours_per_week=8, deadline="2026-08-15",
    ))
    res = evaluate_agent_output("plan_generator", plan)
    assert res.passed, res.checks
    assert res.score >= 0.8


def test_plan_rubric_fails_on_empty_plan():
    res = evaluate_agent_output("plan_generator", {"plan_id": "x", "learner_id": "L",
                                                   "cert_id": "C", "weeks": [],
                                                   "total_planned_hours": 0})
    assert not res.passed
    failed = {c["id"] for c in res.checks if not c["passed"]}
    assert {"P2", "P3", "P4"} & failed


# ── curator ──────────────────────────────────────────────────────────────────
def test_curator_rubric_pass_and_fail():
    good = [{"title": "Functions", "domain": "Compute", "hours": 4,
             "citations": [{"doc_id": "cert_guide", "span_id": "s1"}], "ms_learn_url": ""}]
    assert evaluate_agent_output("curator", good).passed

    uncited = [{"title": "Functions", "domain": "Compute", "hours": 4,
                "citations": [], "ms_learn_url": ""}]
    r = evaluate_agent_output("curator", uncited)
    assert not r.passed
    assert any(c["id"] == "C2" and not c["passed"] for c in r.checks)


# ── readiness_critic ─────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_critic_rubric_with_real_forecast():
    forecast = await compute_readiness_forecast.fn(ForecastInput(
        learner_id="L-1004", cert_id="AZ-204", plan_id="p1",
        evidence_json=json.dumps({"compute": 0.7, "security": 0.4}),
    ))
    critic = {
        "objections": [{"objection_id": "O1", "plan_element_id": "week_2",
                        "severity": "red", "description": "Security under-allocated",
                        "recommendation": "Add 3h", "citation": "cert_guide D3"}],
        "forecast": forecast, "domain_mastery": {}, "overall_risk": "high",
    }
    assert evaluate_agent_output("readiness_critic", critic).passed


def test_critic_rubric_rejects_bad_severity():
    bad = {"objections": [{"severity": "purple", "description": "x", "recommendation": "y"}],
           "forecast": {}, "overall_risk": "unknown"}
    r = evaluate_agent_output("readiness_critic", bad)
    assert not r.passed


# ── assessment ───────────────────────────────────────────────────────────────
def test_assessment_rubric():
    good = {"readiness_verdict": "not_ready", "recommendation": "remediate",
            "pass_probability": 0.42,
            "sample_questions": [{"question_text": "Q", "domain": "D", "citation": "cert_guide"}]}
    assert evaluate_agent_output("assessment", good).passed

    bad = {"readiness_verdict": "maybe", "recommendation": "wait", "pass_probability": 2.0,
           "sample_questions": [{"question_text": "Q", "domain": "D", "citation": ""}]}
    assert not evaluate_agent_output("assessment", bad).passed


# ── engagement ───────────────────────────────────────────────────────────────
def test_engagement_rubric():
    good = {"recommended_study_slots": ["Tue 08:00"], "capacity_risk": "high",
            "ai_disclosure": "AI-generated engagement schedule; does not write to calendar"}
    assert evaluate_agent_output("engagement", good).passed
    bad = {"recommended_study_slots": [], "capacity_risk": "extreme", "ai_disclosure": ""}
    assert not evaluate_agent_output("engagement", bad).passed


# ── manager_insights (privacy-sensitive) ─────────────────────────────────────
def test_manager_rubric_blocks_leaked_score():
    leaked = {"readiness_distribution": {"on_track": 1, "at_risk": 1},
              "manager_actions": ["Protect study time"],
              "summary": "L-1004 estimated_exam_score 640 below threshold",
              "peer_learning_pairs": []}
    r = evaluate_agent_output("manager_insights", leaked)
    assert any(c["id"] == "M3" and not c["passed"] for c in r.checks)

    clean = {"readiness_distribution": {"on_track": 1, "at_risk": 1},
             "manager_actions": ["Protect study time"],
             "summary": "Team of 3: 1 on track, 1 at risk.",
             "peer_learning_pairs": [{"learner_a": "L-1004", "strength": "compute",
                                      "learner_b": "L-1007", "gap": "security"}]}
    assert evaluate_agent_output("manager_insights", clean).passed


# ── batch summary ────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_batch_evaluate_pipeline_quality():
    plan = await generate_study_plan.fn(StudyPlanInput(
        learner_id="L-1004", cert_id="AZ-204",
        curated_topics_json=json.dumps([{"title": "Functions", "domain": "Compute", "hours": 4}]),
        available_hours_per_week=8, deadline="2026-08-15",
    ))
    summary = batch_evaluate({
        "plan_generator": plan,
        "engagement": {"recommended_study_slots": ["Tue 08:00"], "capacity_risk": "low",
                       "ai_disclosure": "does not write to calendar"},
    })
    assert summary["all_passed"]
    assert summary["mean_score"] >= 0.8
