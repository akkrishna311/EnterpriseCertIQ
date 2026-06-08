"""Tests for the deterministic tier-3 agent fallbacks (zero-model demo resilience)."""
import pytest

from backend.agents.fallbacks import build_fallback
from backend.evals.agent_rubrics import evaluate_agent_output
from backend.models import (
    CuratedTopicList, EngagementOutput, AssessmentOutput, CriticOutput, StudyPlan,
)
from backend.main import _load_learner


def _ctx():
    learner = _load_learner("L-1004")
    return {"learner_obj": learner, "learner_id": learner.learner_id,
            "cert_id": learner.cert_target, "team_id": learner.team_id}


@pytest.mark.asyncio
async def test_curator_fallback_is_valid_and_cited():
    topics = await build_fallback("curator", _ctx())
    model = CuratedTopicList.model_validate(topics)  # schema-valid
    assert len(model.root) >= 1
    assert all(t.citations for t in model.root)  # every topic cited
    assert evaluate_agent_output("curator", topics).passed


@pytest.mark.asyncio
async def test_plan_fallback_is_valid_studyplan():
    plan = await build_fallback("plan_generator", _ctx())
    StudyPlan.model_validate(plan)
    assert plan["status"] == "draft"
    assert len(plan["weeks"]) >= 1
    assert evaluate_agent_output("plan_generator", plan).passed


@pytest.mark.asyncio
async def test_critic_fallback_objections_well_formed():
    critic = await build_fallback("readiness_critic", _ctx())
    CriticOutput.model_validate(critic)
    assert critic["overall_risk"] in {"high", "medium", "low"}
    assert evaluate_agent_output("readiness_critic", critic).passed


@pytest.mark.asyncio
async def test_engagement_fallback_uses_work_iq():
    eng = await build_fallback("engagement", _ctx())
    EngagementOutput.model_validate(eng)
    assert eng["recommended_study_slots"]
    assert eng["capacity_risk"] in {"low", "medium", "high"}
    assert evaluate_agent_output("engagement", eng).passed


@pytest.mark.asyncio
async def test_assessment_fallback_verdict_consistent():
    a = await build_fallback("assessment", _ctx())
    AssessmentOutput.model_validate(a)
    assert a["readiness_verdict"] in {"ready", "not_ready", "insufficient_evidence"}
    assert evaluate_agent_output("assessment", a).passed


@pytest.mark.asyncio
async def test_intake_fallback_text():
    intake = await build_fallback("learner_intake", _ctx())
    assert isinstance(intake, str) and "L-1004" in intake


@pytest.mark.asyncio
async def test_retrospective_fallback_is_structured_and_valid():
    retro = await build_fallback("retrospective", _ctx())
    assert isinstance(retro, dict)
    assert retro["root_cause"] in {"engagement_gap", "retrieval_quality",
                                   "plan_quality", "skill_gap", "mixed"}
    assert retro.get("recovery_recommendations")
    assert evaluate_agent_output("retrospective", retro).passed


@pytest.mark.asyncio
async def test_force_mode_runs_full_pipeline_without_model(monkeypatch):
    """End-to-end: force mode produces a complete run with zero model calls."""
    monkeypatch.setenv("AGENT_FALLBACK_MODE", "force")
    from config.settings import get_settings
    get_settings.cache_clear()  # pick up the env override
    try:
        from backend.agents.factory import build_agents
        from backend.core.workflow import WorkflowOrchestrator
        agents = build_agents()
        wf = WorkflowOrchestrator(
            intake_agent=agents["intake"], curator_agent=agents["curator"],
            planner_agent=agents["planner"], critic_agent=agents["critic"],
            engagement_agent=agents["engagement"], manager_agent=agents["manager"],
            assessment_agent=agents["assessment"], retrospective_agent=agents["retrospective"],
        )
        ctx = await wf.run(_load_learner("L-1004"))
        assert {"curator", "final_plan", "engagement", "assessment", "manager"} <= set(ctx.outputs)
        assert isinstance(ctx.outputs["final_plan"], dict)
        assert len(ctx.outputs["final_plan"]["weeks"]) >= 1
    finally:
        get_settings.cache_clear()
