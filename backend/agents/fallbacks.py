"""
Deterministic 3rd-tier agent fallbacks.

Tier 1 = configured model (Foundry Local / Azure AI Foundry).
Tier 2 = bounded retry on transient errors (BaseAgent._model_call).
Tier 3 = these deterministic builders — pure Python over the synthetic data, the
         IQ layers, and the MCP tools. No model, no network, no credentials.

Why: a fully deterministic demo path that never fails on missing credentials or
transient outages. Set `AGENT_FALLBACK_MODE=force` for a zero-credential demo, or
leave it on `auto` so a model outage degrades gracefully instead of breaking the
pipeline.

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
    import json
    from pathlib import Path
    from config.settings import get_settings

    learner = _learner_obj(context)
    team_id = context.get("team_id", getattr(learner, "team_id", "TEAM-A"))

    # Load team roster and all learner profiles from synthetic store
    data_dir = Path(get_settings().data_dir) / "synthetic"
    try:
        teams_raw = json.loads((data_dir / "teams.json").read_text())
        learners_raw = json.loads((data_dir / "learners.json").read_text())
    except Exception:
        teams_raw, learners_raw = [], []

    team = next((t for t in teams_raw if t.get("team_id") == team_id), None)
    member_ids: list[str] = team.get("members", []) if team else (
        [getattr(learner, "learner_id", "L-0000")] if learner else []
    )
    members = [l for l in learners_raw if l.get("learner_id") in member_ids]

    # Capacity risk per member
    capacity_conflicts: list[str] = []
    at_risk = 0
    on_track = 0
    for m in members:
        sig = m.get("work_iq_signals", {})
        mtg = sig.get("meeting_hours_per_week", 0)
        if mtg >= 25:
            at_risk += 1
            capacity_conflicts.append(m["learner_id"])
        else:
            on_track += 1
    insuff = max(0, len(members) - on_track - at_risk)

    # Peer learning pairs: match on complementary domain mastery
    # Use prior_assessment_evidence as a mastery proxy
    peer_pairs = []
    paired: set = set()
    for i, m_a in enumerate(members):
        if m_a["learner_id"] in paired:
            continue
        ev_a = m_a.get("prior_assessment_evidence") or {}
        if not ev_a:
            continue
        # Find the weakest domain for m_a
        weakest = min(ev_a, key=lambda k: ev_a[k]) if ev_a else None
        if weakest is None:
            continue
        # Find a peer who is stronger in that domain and shares the same cert target
        for m_b in members[i + 1:]:
            if m_b["learner_id"] in paired:
                continue
            if m_b.get("cert_target") != m_a.get("cert_target"):
                continue
            ev_b = m_b.get("prior_assessment_evidence") or {}
            strength_b = ev_b.get(weakest, 0)
            gap_a = ev_a.get(weakest, 0)
            if strength_b - gap_a >= 0.10:
                peer_pairs.append({
                    "learner_a": m_b["learner_id"],
                    "learner_b": m_a["learner_id"],
                    "gap": weakest,
                    "rationale": (
                        f"{m_b['learner_id']} is stronger in {weakest.replace('_', ' ')} "
                        f"({int(strength_b * 100)}%) and can mentor "
                        f"{m_a['learner_id']} ({int(gap_a * 100)}%)."
                    ),
                })
                paired.add(m_a["learner_id"])
                paired.add(m_b["learner_id"])
                break

    # Manager actions derived from capacity and evidence
    actions: list[str] = []
    if capacity_conflicts:
        actions.append(
            f"Protect study blocks for {', '.join(capacity_conflicts)} — meeting load >25 h/wk."
        )
    if peer_pairs:
        actions.append(
            f"Facilitate {len(peer_pairs)} peer-learning session(s) flagged by domain mastery gap."
        )
    actions.append("Run mock assessments for all team members before deadline.")

    risk_areas: list[str] = []
    if capacity_conflicts:
        risk_areas.append(
            f"{len(capacity_conflicts)} member(s) carry >25 h/wk meetings — study completion at risk."
        )
    risk_areas.append("Ensure all learners complete at least one practice exam before certification date.")

    summary = (
        f"Team {team_id} — {len(members)} member(s). "
        f"{on_track} on track, {at_risk} at capacity risk. "
        f"{len(peer_pairs)} peer-learning pair(s) identified by domain mastery gap. {_DISCLOSURE}."
    )

    return {
        "team_id": team_id,
        "summary": summary,
        "readiness_distribution": {
            "on_track": on_track,
            "at_risk": at_risk,
            "insufficient_evidence": insuff,
        },
        "capacity_conflicts": capacity_conflicts,
        "risk_areas": risk_areas,
        "peer_learning_pairs": peer_pairs,
        "manager_actions": actions,
        "ai_disclosure": _DISCLOSURE,
    }


async def _fallback_audio(context: dict) -> dict:
    """A grounded two-host script. Concept mode deep-teaches one domain; overview mode
    sweeps the exam domains."""
    from backend.iq.fabric_iq import get_fabric_iq
    cert_id = context.get("cert_id", "")
    learner = _learner_obj(context)
    learner_id = context.get("learner_id", getattr(learner, "learner_id", ""))
    thresholds = context.get("domains") or get_fabric_iq().get_domain_thresholds(cert_id)
    forecast = context.get("forecast") or {}
    weak = forecast.get("weakest_topic", "")

    # ── Concept mode: deep-teach one domain ──────────────────────────────────
    focus = context.get("focus_domain")
    if context.get("mode") == "concept" and focus:
        services = focus.get("services", [])
        svc = ", ".join(services[:4]) or "the core services"
        svc1 = services[0] if services else "the primary service"
        svc2 = services[1] if len(services) > 1 else svc1
        weight = int(focus.get("weight_pct", 0))
        excerpt = (context.get("excerpts") or [{}])[0].get("excerpt", "")
        why = ("It's your weakest, highest-leverage area right now"
               if context.get("is_weakest") else "You picked this concept to focus on")
        c_turns = [
            {"speaker": "host_a", "text": f"Welcome to a focused episode on {focus['name']} for {cert_id}. "
                                          f"{why}, and it's about {weight} percent of the exam — so it's worth real points."},
            {"speaker": "host_b", "text": "Let's get into it. What exactly does this concept cover?"},
            {"speaker": "host_a", "text": f"At its core, {focus['name']} is about working with {svc}. "
                                          + (f"From the approved guide: {excerpt[:160]}" if excerpt else "")},
            {"speaker": "host_b", "text": "Why does it matter so much for the exam?"},
            {"speaker": "host_a", "text": f"Because it carries {weight} percent of the weight, you'll see "
                                          f"several scenario questions here — especially around {svc1} and {svc2}."},
            {"speaker": "host_b", "text": "Can you walk me through a concrete example?"},
            {"speaker": "host_a", "text": f"Sure. Imagine you need to design a solution using {svc1}. "
                                          f"You'd reach for {svc1} when the requirement calls for it, and pair it with "
                                          f"{svc2} where they complement each other. Match the service to the requirement."},
            {"speaker": "host_b", "text": "What's a common mistake people make?"},
            {"speaker": "host_a", "text": f"A frequent trap is picking a familiar service instead of the one that fits the "
                                          f"stated constraint. Always anchor on what {focus['name'].lower()} actually requires."},
            {"speaker": "host_b", "text": "Give me a quick self-check before we wrap?"},
            {"speaker": "host_a", "text": f"Here's one: for a {focus['name'].lower()} scenario, which of {svc1} or {svc2} "
                                          f"best fits, and why? Pause, answer it out loud, then confirm against the guide."},
            {"speaker": "host_a", "text": f"That's {focus['name']}. Put one focused session here, then take a short quiz to lock it in."},
        ]
        return {
            "title": f"{cert_id}: {focus['name']} — Deep Dive",
            "cert_id": cert_id, "learner_id": learner_id, "turns": c_turns,
            "citations": [f"{cert_id}: Key Topics by Domain",
                          f"cert_structures: {focus.get('domain_id', '')} ({weight}%)"],
            "ai_disclosure": f"{_DISCLOSURE} (concept podcast)",
        }

    # ── Overview mode: sweep the exam domains ────────────────────────────────
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


async def _fallback_retrospective(context: dict) -> dict:
    from backend.iq.fabric_iq import get_fabric_iq
    learner = _learner_obj(context)
    cert_id = context.get("cert_id", getattr(learner, "cert_target", ""))
    attempts = getattr(learner, "prior_attempts", []) if learner else []
    n = len(attempts)

    # Pull the most recent attempt's data if available
    last = None
    if attempts:
        last_raw = attempts[-1]
        last = last_raw.model_dump() if hasattr(last_raw, "model_dump") else dict(last_raw)

    prior_score = last.get("score") if last else None
    prior_date = last.get("date") if last else None
    weak_areas = last.get("weak_areas", []) if last else []

    # Root cause heuristic: check capacity vs skill gap
    work_signals = getattr(learner, "work_iq_signals", None) if learner else None
    meeting_hrs = getattr(work_signals, "meeting_hours_per_week", 20) if work_signals else 20
    available_hrs = getattr(work_signals, "available_study_hours_per_week", 0) if work_signals else 0

    if meeting_hrs >= 25:
        root_cause = "engagement_gap"
        evidence_msg = f"Meeting load {meeting_hrs}h/wk left only {available_hrs}h for study — plan adherence was structurally compromised."
    elif weak_areas:
        root_cause = "skill_gap"
        evidence_msg = f"Weak areas identified: {', '.join(str(w) for w in weak_areas[:3])}. These domains were under-weighted in the prior plan."
    else:
        root_cause = "plan_quality"
        evidence_msg = "Prior plan likely under-allocated high-leverage domains based on cert structure weights."

    # Compute extra hours recommendation from Fabric IQ semantic weights
    thresholds = get_fabric_iq().get_domain_thresholds(cert_id)
    high_leverage = [d for d in thresholds if d.get("priority") == "high"]
    extra_hours: dict = {d["name"]: round(d["weight_pct"] / 10, 1) for d in high_leverage[:3]}

    return {
        "learner_id": getattr(learner, "learner_id", "L-0000"),
        "prior_attempt_date": prior_date or "unknown",
        "prior_score": prior_score,
        "root_cause": root_cause,
        "evidence": [
            evidence_msg,
            f"{n} prior attempt(s) reviewed.",
            "Remediation should front-load highest-leverage domains before re-sitting.",
        ],
        "recovery_recommendations": [
            "Use short daily sessions (30–45 min) instead of weekly blocks.",
            f"Focus first on: {', '.join(str(w) for w in weak_areas[:2]) or 'highest-weight cert domain'}.",
            "Schedule a mock exam before re-sitting the real exam.",
        ],
        "next_plan_adjustments": {
            "extra_hours_on_weak_areas": extra_hours,
            "session_length_preference": "short_daily",
        },
        "ai_disclosure": f"AI-generated postmortem; system self-assessment only. {_DISCLOSURE}",
    }


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
