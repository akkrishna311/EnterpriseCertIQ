"""
Deterministic 3rd-tier agent fallbacks.

Tier 1 = configured model (Foundry Local / Azure AI Foundry).
Tier 2 = bounded retry on transient errors (BaseAgent._model_call).
Tier 3 = these deterministic builders — pure Python over the synthetic data, the
         IQ layers, and the MCP tools. No model, no network, no credentials.

Why: the competitor won a prior league partly on a zero-credential demo path that
never fails in front of judges. This gives EnterpriseCertIQ the same guarantee —
set `AGENT_FALLBACK_MODE=force` for a fully deterministic demo, or leave it on
`auto` so a model outage degrades gracefully instead of breaking the pipeline.

Every builder returns data matching the agent's `response_format` (or a string for
the unstructured intake/retrospective agents). Outputs carry an explicit
"deterministic fallback" disclosure so they are never mistaken for model reasoning.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_DISCLOSURE = "Deterministic fallback (no model) — derived from approved synthetic data"


def _learner_obj(context: dict):
    return context.get("learner_obj")


def _evidence_from_context(context: dict) -> dict:
    if context.get("evidence"):
        return context["evidence"]
    learner = _learner_obj(context)
    if learner is not None and getattr(learner, "prior_assessment_evidence", None):
        ev = learner.prior_assessment_evidence
        return ev.model_dump() if hasattr(ev, "model_dump") else dict(ev)
    return {}


async def _fallback_intake(context: dict) -> str:
    from backend.mcp_server.server import parse_learner_profile, LearnerProfileInput
    learner = _learner_obj(context)
    if learner is None:
        return "Learner profile unavailable; using cohort baselines."
    res = await parse_learner_profile.fn(LearnerProfileInput(
        learner_id=learner.learner_id, cert_target=learner.cert_target,
        raw_profile_json=learner.model_dump_json(),
    ))
    return res.get("summary", "") + f"\n[{_DISCLOSURE}]"


async def _fallback_curator(context: dict) -> list[dict]:
    """Topics straight from the cert ontology — one per weighted domain, cited."""
    from backend.iq.fabric_iq import get_fabric_iq
    cert_id = context.get("cert_id", "")
    thresholds = get_fabric_iq().get_domain_thresholds(cert_id)
    topics = []
    for d in thresholds:
        # Higher-leverage domains get more hours.
        hours = round(min(12.0, max(2.0, d["weight_pct"] / 6)), 1)
        topics.append({
            "title": d["name"][:120],
            "domain": d["name"][:60],
            "hours": hours,
            "priority": "high" if d["priority"] == "high" else "medium",
            "citations": [{
                "doc_id": "cert_structures",
                "title": f"{cert_id} Certification Guide",
                "span_id": d["domain_id"],
                "excerpt": f"{d['name']} — {d['weight_pct']}% of exam. Services: "
                           + ", ".join(d.get("services", [])[:3]),
                "source_url": "",
            }],
            "ms_learn_url": "",
        })
    return topics or [{
        "title": "Foundations", "domain": "General", "hours": 3, "priority": "medium",
        "citations": [{"doc_id": "cert_structures", "title": "Guide", "span_id": "D0",
                       "excerpt": "Foundational study.", "source_url": ""}],
        "ms_learn_url": "",
    }]


async def _fallback_plan(context: dict) -> dict:
    from backend.mcp_server.server import generate_study_plan, StudyPlanInput
    learner = _learner_obj(context)
    cert_id = context.get("cert_id", getattr(learner, "cert_target", ""))
    topics = context.get("curated_topics") or await _fallback_curator(context)
    hours = (learner.work_iq_signals.available_study_hours_per_week
             if learner is not None else 6.0) or 6.0
    deadline = getattr(learner, "deadline", "") or "2026-12-31"
    learner_id = getattr(learner, "learner_id", context.get("learner_id", "L-0000"))
    return await generate_study_plan.fn(StudyPlanInput(
        learner_id=learner_id, cert_id=cert_id,
        curated_topics_json=json.dumps(topics),
        available_hours_per_week=hours, deadline=deadline,
    ))


async def _fallback_critic(context: dict) -> dict:
    from backend.mcp_server.server import (
        compute_readiness_forecast, ForecastInput,
        compute_domain_mastery, DomainMasteryInput,
    )
    from backend.iq.fabric_iq import get_fabric_iq
    learner = _learner_obj(context)
    cert_id = context.get("cert_id", getattr(learner, "cert_target", ""))
    learner_id = getattr(learner, "learner_id", "L-0000")
    evidence = _evidence_from_context(context)

    forecast = await compute_readiness_forecast.fn(ForecastInput(
        learner_id=learner_id, cert_id=cert_id, plan_id="fallback",
        evidence_json=json.dumps(evidence),
    ))
    mastery = await compute_domain_mastery.fn(DomainMasteryInput(
        learner_id=learner_id, cert_id=cert_id, evidence_json=json.dumps(evidence),
    ))
    # Objections on the highest-leverage under-mastered domains.
    sem = get_fabric_iq().get_readiness_semantics(cert_id, evidence)
    objections = []
    for i, d in enumerate(sem.get("domains", [])):
        if d.get("gap") and d["gap"] > 0.1:
            objections.append({
                "objection_id": f"O{i+1}", "plan_element_id": d.get("domain_id", ""),
                "severity": "red" if (d["gap"] * d["leverage"]) > 0.05 else "amber",
                "description": f"{d['name']} mastery {int((d['avg_mastery'] or 0)*100)}% "
                               f"vs target {int(d['minimum_mastery']*100)}% "
                               f"({int(d['weight_pct'])}% of exam).",
                "recommendation": f"Add focused study on {d['name']}.",
                "citation": f"cert_structures: {d.get('domain_id','')} weight {int(d['weight_pct'])}%",
            })
    overall = "high" if any(o["severity"] == "red" for o in objections) else (
        "medium" if objections else "low")
    return {
        "objections": objections[:5], "forecast": forecast, "domain_mastery": mastery,
        "overall_risk": overall, "ai_disclosure": _DISCLOSURE,
    }


async def _fallback_engagement(context: dict) -> dict:
    from backend.iq.work_iq import get_work_iq
    learner = _learner_obj(context)
    if learner is None:
        return {"recommended_study_slots": ["Tuesday 08:00-09:30"], "capacity_risk": "medium",
                "ai_disclosure": f"{_DISCLOSURE}; does not write to calendar"}
    wc = await get_work_iq().get_work_context(learner)
    return {
        "employee_id": learner.learner_id,
        "recommended_study_slots": wc.recommended_slots,
        "blocked_periods": wc.busy_periods,
        "engagement_strategy": f"Study during {learner.work_iq_signals.preferred_learning_slot.lower()} "
                               "focus windows; protect blocks before milestones.",
        "capacity_risk": wc.capacity_risk,
        "replan_trigger": wc.capacity_risk == "high",
        "ai_disclosure": f"{_DISCLOSURE}; does not write to calendar",
    }


async def _fallback_assessment(context: dict) -> dict:
    from backend.mcp_server.server import compute_readiness_forecast, ForecastInput
    learner = _learner_obj(context)
    cert_id = context.get("cert_id", getattr(learner, "cert_target", ""))
    learner_id = getattr(learner, "learner_id", "L-0000")
    forecast = context.get("forecast")
    if not forecast:
        forecast = await compute_readiness_forecast.fn(ForecastInput(
            learner_id=learner_id, cert_id=cert_id, plan_id="fallback",
            evidence_json=json.dumps(_evidence_from_context(context)),
        ))
    if forecast.get("insufficient_evidence"):
        verdict, rec = "insufficient_evidence", "gather_evidence"
    elif forecast.get("estimated_exam_score", 0) >= forecast.get("pass_threshold", 700):
        verdict, rec = "ready", "advance"
    else:
        verdict, rec = "not_ready", "remediate"
    weak = forecast.get("weakest_topic", "")
    return {
        "learner_id": learner_id, "cert_id": cert_id,
        "readiness_verdict": verdict, "recommendation": rec,
        "pass_probability": forecast.get("pass_probability", 0.0),
        "estimated_exam_score": forecast.get("estimated_exam_score", 0),
        "pass_threshold": forecast.get("pass_threshold", 700),
        "weak_areas": [weak] if weak else [],
        "sample_questions": [],
        "next_step": "", "rationale": f"Forecast-driven verdict. {_DISCLOSURE}.",
        "ai_disclosure": _DISCLOSURE,
    }


async def _fallback_manager(context: dict) -> dict:
    learner = _learner_obj(context)
    team_id = context.get("team_id", getattr(learner, "team_id", "TEAM"))
    return {
        "team_id": team_id,
        "summary": f"Team {team_id}: deterministic readiness summary (model unavailable).",
        "readiness_distribution": {"on_track": 0, "at_risk": 1, "insufficient_evidence": 0},
        "capacity_conflicts": [],
        "risk_areas": ["Generated without model — see /api/manager/{team}/insights for full analysis."],
        "peer_learning_pairs": [],
        "manager_actions": ["Review the full manager insights endpoint for Fabric IQ skill gaps."],
        "ai_disclosure": _DISCLOSURE,
    }


async def _fallback_audio(context: dict) -> dict:
    """A grounded two-host briefing script built from the cert ontology + forecast."""
    from backend.iq.fabric_iq import get_fabric_iq
    cert_id = context.get("cert_id", "")
    learner = _learner_obj(context)
    learner_id = context.get("learner_id", getattr(learner, "learner_id", ""))
    thresholds = context.get("domains") or get_fabric_iq().get_domain_thresholds(cert_id)
    forecast = context.get("forecast") or {}
    weak = forecast.get("weakest_topic", "")

    turns = [
        {"speaker": "host_a", "text": f"Welcome to your {cert_id} study briefing. "
                                      "We'll walk through the exam domains and where to focus your time."},
        {"speaker": "host_b", "text": "Sounds good. Which areas carry the most weight?"},
    ]
    for d in sorted(thresholds, key=lambda x: x.get("weight_pct", 0), reverse=True)[:5]:
        svc = ", ".join(d.get("services", [])[:3])
        turns.append({"speaker": "host_a",
                      "text": f"{d['name']} is about {int(d['weight_pct'])} percent of the exam. "
                              f"Key areas include {svc}." if svc else
                              f"{d['name']} is about {int(d['weight_pct'])} percent of the exam."})
        turns.append({"speaker": "host_b",
                      "text": f"Got it, so {d['name'].lower()} is worth real points."})
    if weak:
        turns.append({"speaker": "host_a",
                      "text": f"Based on your readiness forecast, start with {weak} — "
                              "it's your weakest area right now."})
        turns.append({"speaker": "host_b", "text": "Makes sense. I'll prioritise that first."})
    turns.append({"speaker": "host_a",
                  "text": "You've got this. Keep sessions short and focused, and take a full "
                          "mock exam before test day. Good luck!"})

    citations = [f"{cert_id}: Key Topics by Domain"] + [
        f"cert_structures: {d.get('domain_id', '')} ({int(d.get('weight_pct', 0))}%)"
        for d in thresholds[:3]
    ]
    return {
        "title": f"{cert_id} Audio Study Briefing",
        "cert_id": cert_id, "learner_id": learner_id,
        "turns": turns, "citations": citations,
        "ai_disclosure": f"{_DISCLOSURE} (audio briefing script)",
    }


async def _fallback_retrospective(context: dict) -> str:
    learner = _learner_obj(context)
    attempts = getattr(learner, "prior_attempts", []) if learner else []
    n = len(attempts)
    return (f"Retrospective (deterministic): {n} prior attempt(s) reviewed. "
            "Likely contributors: under-allocated high-leverage domains and capacity "
            f"pressure. Recommend targeted remediation on the weakest domain. [{_DISCLOSURE}]")


_BUILDERS = {
    "learner_intake": _fallback_intake,
    "curator": _fallback_curator,
    "plan_generator": _fallback_plan,
    "readiness_critic": _fallback_critic,
    "engagement": _fallback_engagement,
    "assessment": _fallback_assessment,
    "manager_insights": _fallback_manager,
    "retrospective": _fallback_retrospective,
    "audio_curriculum": _fallback_audio,
}


async def build_fallback(agent_name: str, context: Optional[dict]) -> Any:
    """Return a deterministic, schema-shaped output for `agent_name`."""
    builder = _BUILDERS.get(agent_name)
    if builder is None:
        return f"[{_DISCLOSURE}] No deterministic builder for '{agent_name}'."
    return await builder(context or {})
