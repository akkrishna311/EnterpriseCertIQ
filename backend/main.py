"""
EnterpriseCertIQ — FastAPI backend
Provides REST + SSE endpoints for the React dashboard.
"""
from __future__ import annotations

# Load ALL vars from .env.local into os.environ before any Azure SDK is imported.
# Pydantic BaseSettings only maps declared fields; this ensures AZURE_CLIENT_ID /
# AZURE_CLIENT_SECRET / AZURE_TENANT_ID reach DefaultAzureCredential's EnvironmentCredential.
from dotenv import load_dotenv as _load_dotenv
_load_dotenv(".env.local", override=False)
_load_dotenv(".env", override=False)

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Optional

import structlog
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from backend.agents.factory import build_agents
from backend.core.telemetry import setup_telemetry
from backend.core.workflow import WorkflowOrchestrator
from backend.models.learner import LearnerProfile, PriorAttempt
from backend.models.trace import TraceEvent, TraceEventType
from backend.storage.store import get_storage
from config.settings import get_settings

logging.basicConfig(level=logging.INFO)
logger = structlog.get_logger()

s = get_settings()
storage = get_storage()

# ── Event bus (in-memory SSE fan-out) ─────────────────────────────────────
_sse_queues: dict[str, asyncio.Queue] = {}


def _broadcast(run_id: str, event: TraceEvent) -> None:
    q = _sse_queues.get(run_id)
    if q:
        try:
            q.put_nowait(event.model_dump())
        except asyncio.QueueFull:
            pass


# ── App lifespan ───────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load secrets from Key Vault first (no-op when AZURE_KEY_VAULT_URL is unset)
    # so telemetry/model/search/cosmos all see the resolved secrets.
    from config.key_vault import load_key_vault_secrets
    kv = load_key_vault_secrets()
    if kv.get("enabled"):
        logger.info("Key Vault: %d secret(s) loaded", kv.get("loaded", 0))
    setup_telemetry()
    from backend.core.telemetry import (
        instrument_fastapi, instrument_foundry_agents, shutdown_telemetry,
    )
    instrument_fastapi(app)  # per-call request spans → App Insights
    instrument_foundry_agents()  # GenAI/agent spans → Foundry project Tracing tab
    # Pre-register agent definitions in Foundry Agent Service (Azure mode only; no-op locally)
    from backend.core.foundry_orchestration import register_all_agents
    registered = await register_all_agents()
    if registered:
        logger.info("Foundry agents registered: %d", len(registered))
    logger.info("EnterpriseCertIQ starting", backend=s.model_backend.value)
    yield
    shutdown_telemetry()  # flush buffered spans
    logger.info("EnterpriseCertIQ shutting down")


app = FastAPI(
    title="EnterpriseCertIQ API",
    version="1.2.0",
    description="Multi-agent enterprise certification learning system",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=s.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ──────────────────────────────────────────────

class RunWorkflowRequest(BaseModel):
    learner_id: str
    cert_target: Optional[str] = None


class ApproveRequest(BaseModel):
    plan_id: str
    approved_by: str = "human"


class AssessmentSubmitRequest(BaseModel):
    assessment_id: str
    learner_id: str
    cert_id: str
    answers: dict[str, int]


class PeerLearningSessionRequest(BaseModel):
    id: str
    mentor_id: str
    learner_id: str
    cert_id: str
    focus_domain: str
    suggested_slot: Optional[str] = None
    rationale: str
    owner_id: str = "manager"
    status: str = "planned"
    manager_note: str = ""


class ManagerInterventionRequest(BaseModel):
    id: str
    learner_id: str
    priority: str
    reasons: list[str]
    owner_id: str = "manager"
    status: str = "planned"
    manager_note: str = ""


class ManagerWhatIfRequest(BaseModel):
    target_learner_id: str
    protected_focus_hours: float = 0.0
    reduced_meeting_hours: float = 0.0
    targeted_review_hours: float = 0.0
    peer_mentor_id: Optional[str] = None
    peer_session_count: int = 1


# ── Helpers ────────────────────────────────────────────────────────────────

def _load_learner(learner_id: str) -> LearnerProfile:
    import json
    from pathlib import Path
    path = Path(s.data_dir) / "synthetic" / "learners.json"
    learners = json.loads(path.read_text())
    raw = next((l for l in learners if l["learner_id"] == learner_id), None)
    if not raw:
        raise HTTPException(status_code=404, detail=f"Learner {learner_id} not found")
    return LearnerProfile(**raw)


def _load_all_learners() -> list[LearnerProfile]:
    import json
    from pathlib import Path
    path = Path(s.data_dir) / "synthetic" / "learners.json"
    return [LearnerProfile(**l) for l in json.loads(path.read_text())]


def _load_teams() -> list[dict]:
    import json
    from pathlib import Path
    path = Path(s.data_dir) / "synthetic" / "teams.json"
    return json.loads(path.read_text())


def _pass_threshold_for_cert(cert_id: str) -> int:
    from pathlib import Path

    path = Path(s.data_dir) / "synthetic" / "cert_structures.json"
    if not path.exists():
        return 700
    structures = json.loads(path.read_text())
    return int(structures.get(cert_id, {}).get("passing_score", 700))


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _normalise_evidence(evidence: dict) -> dict[str, float]:
    return {
        key: float(value)
        for key, value in evidence.items()
        if isinstance(value, (int, float))
    }


def _evidence_for_manager_summary(learner: LearnerProfile, latest_assessment: Optional[dict]) -> dict:
    if latest_assessment and isinstance(latest_assessment.get("evidence"), dict):
        return latest_assessment["evidence"]
    evidence = learner.prior_assessment_evidence
    if evidence is None:
        return {}
    # prior_assessment_evidence is a Pydantic model — convert to a dict so it
    # actually feeds readiness/skill-gap (previously dropped → false "insufficient").
    if hasattr(evidence, "model_dump"):
        return evidence.model_dump()
    return evidence if isinstance(evidence, dict) else {}


def _average_evidence_score(evidence: dict) -> float:
    values = [value for value in evidence.values() if isinstance(value, (int, float))]
    if not values:
        return 0.0
    return sum(values) / len(values)


def _sorted_strengths(evidence: dict) -> list[tuple[str, float]]:
    items = [(key, float(value)) for key, value in evidence.items() if isinstance(value, (int, float))]
    return sorted(items, key=lambda item: item[1], reverse=True)


async def _build_manager_peer_pairs(team_id: str, learners: list[LearnerProfile]) -> list[dict]:
    learner_states = []
    for learner in learners:
        latest = await _latest_submitted_assessment(learner.learner_id, learner.cert_target)
        evidence = _evidence_for_manager_summary(learner, latest)
        learner_states.append({
            "learner": learner,
            "latest": latest,
            "evidence": evidence,
            "strengths": _sorted_strengths(evidence),
            "avg": _average_evidence_score(evidence),
        })

    pairs: list[dict] = []
    for state in learner_states:
        learner = state["learner"]
        strengths = state["strengths"]
        if not strengths:
          continue
        weakest_area = strengths[-1][0]
        latest = state["latest"]
        if latest and latest.get("passed", False):
            continue
        needs_support = latest is None or strengths[-1][1] < 0.65
        if not needs_support:
            continue

        same_cert_candidates = []
        for candidate_state in learner_states:
            candidate = candidate_state["learner"]
            if candidate.learner_id == learner.learner_id:
                continue
            if candidate.cert_target != learner.cert_target:
                continue
            candidate_evidence = candidate_state["evidence"]
            if weakest_area not in candidate_evidence:
                continue
            strength_delta = float(candidate_evidence[weakest_area]) - float(state["evidence"].get(weakest_area, 0))
            if strength_delta < 0.1:
                continue
            same_cert_candidates.append((strength_delta, candidate_state))

        if same_cert_candidates:
            same_cert_candidates.sort(key=lambda item: item[0], reverse=True)
            mentor_state = same_cert_candidates[0][1]
            mentor = mentor_state["learner"]
            mentor_strength = mentor_state["strengths"][0][0] if mentor_state["strengths"] else weakest_area
            pairs.append({
                "learner_a": mentor.learner_id,
                "strength": mentor_strength,
                "learner_b": learner.learner_id,
                "gap": weakest_area,
                "match_type": "same_cert",
            })
            continue

        cross_cert_candidates = [candidate_state for candidate_state in learner_states if candidate_state["learner"].learner_id != learner.learner_id]
        if not cross_cert_candidates:
            continue
        cross_cert_candidates.sort(
            key=lambda candidate_state: (
                candidate_state["latest"].get("score_pct", -1) if candidate_state["latest"] else -1,
                candidate_state["avg"],
                candidate_state["learner"].work_iq_signals.focus_hours_per_week,
            ),
            reverse=True,
        )
        mentor_state = cross_cert_candidates[0]
        mentor = mentor_state["learner"]
        pairs.append({
            "learner_a": mentor.learner_id,
            "strength": "study_cadence",
            "learner_b": learner.learner_id,
            "gap": "exam_rehearsal",
            "match_type": "cross_cert",
        })

    unique_pairs = []
    seen: set[tuple[str, str, str]] = set()
    for pair in pairs:
        key = (pair["learner_a"], pair["learner_b"], pair["gap"])
        if key in seen:
            continue
        seen.add(key)
        unique_pairs.append(pair)
    return unique_pairs


async def _build_manager_insight_payload(team_id: str, learners: list[LearnerProfile]) -> dict:
    from backend.iq.work_iq import get_work_iq

    wiq = get_work_iq()
    context = await wiq.get_team_context(team_id, learners)
    latest_assessments = {
        learner.learner_id: await _latest_submitted_assessment(learner.learner_id, learner.cert_target)
        for learner in learners
    }

    readiness_distribution = {"on_track": 0, "at_risk": 0, "insufficient_evidence": 0}
    low_evidence_learners: list[str] = []
    below_threshold_learners: list[str] = []
    no_attempt_learners: list[str] = []
    for learner in learners:
        latest = latest_assessments[learner.learner_id]
        evidence = _evidence_for_manager_summary(learner, latest)
        if not evidence:
            readiness_distribution["insufficient_evidence"] += 1
            low_evidence_learners.append(learner.learner_id)
            no_attempt_learners.append(learner.learner_id)
            continue

        avg_evidence = _average_evidence_score(evidence)
        if latest and latest.get("passed"):
            readiness_distribution["on_track"] += 1
        elif latest and latest.get("submitted_at"):
            readiness_distribution["at_risk"] += 1
            below_threshold_learners.append(learner.learner_id)
        elif avg_evidence >= 0.7:
            readiness_distribution["on_track"] += 1
        else:
            readiness_distribution["at_risk"] += 1
            low_evidence_learners.append(learner.learner_id)

    capacity_conflicts = []
    for learner in learners:
        signals = learner.work_iq_signals
        if signals.meeting_hours_per_week > 25:
            milestones = ", ".join(signals.upcoming_milestones) if signals.upcoming_milestones else "upcoming delivery work"
            capacity_conflicts.append(f"{learner.learner_id} has >25 meeting hours and pending milestone pressure from {milestones}.")

    risk_areas = []
    if context["high_capacity_risk_members"]:
        risk_areas.append(f"High meeting load is affecting {len(context['high_capacity_risk_members'])} learner(s).")
    if no_attempt_learners:
        risk_areas.append(f"{len(no_attempt_learners)} learner(s) still need a fresh mock exam signal.")
    if below_threshold_learners:
        risk_areas.append(f"Latest mock attempts are below threshold for {', '.join(below_threshold_learners)}.")

    peer_pairs = await _build_manager_peer_pairs(team_id, learners)
    manager_actions = []
    if context["high_capacity_risk_members"]:
        manager_actions.append("Protect one recurring study block for high-risk learners before the next certification checkpoint.")
    if below_threshold_learners:
        manager_actions.append(f"Queue a remediation mock exam for {below_threshold_learners[0]} after targeted review.")
    if peer_pairs:
        pair = peer_pairs[0]
        manager_actions.append(f"Schedule {pair['learner_a']} to coach {pair['learner_b']} on {pair['gap'].replace('_', ' ')} this week.")
    if not manager_actions:
        manager_actions.append("Maintain the current study cadence and review progress after the next assessment attempt.")

    summary = (
        f"Team {team_id} has {readiness_distribution['on_track']} learner(s) on track, "
        f"{readiness_distribution['at_risk']} at risk, and "
        f"{readiness_distribution['insufficient_evidence']} with insufficient evidence."
    )

    # ── Fabric IQ: semantic team skill-gap meaning + cohort benchmarks ──────
    from backend.iq.fabric_iq import get_fabric_iq

    fiq = get_fabric_iq()
    evidence_by_learner = {
        learner.learner_id: _evidence_for_manager_summary(learner, latest_assessments[learner.learner_id])
        for learner in learners
    }
    member_certs = {learner.learner_id: learner.cert_target for learner in learners}
    skill_gaps = fiq.get_team_skill_gap_summary(
        team_id, evidence_by_learner, member_certs, team_size=len(learners)
    )
    team_certs = sorted(set(member_certs.values()))
    fabric_iq = {
        "skill_gap_summary": skill_gaps,
        "cohort_benchmarks": [fiq.get_cohort_benchmark(cert) for cert in team_certs],
        "intervention_effectiveness": [fiq.get_intervention_effectiveness(cert) for cert in team_certs],
    }
    # Surface the top priority gap as a semantic risk area for the manager.
    if skill_gaps.get("top_priority_gaps"):
        risk_areas.append(skill_gaps["narrative"])

    # ROI cost-of-delay: each month a certified engineer is delayed costs the
    # organisation an estimated fraction of the certification salary uplift.
    _CERT_UPLIFT = {
        "AZ-204": 18000, "AZ-305": 22000, "AZ-104": 14000, "AZ-400": 20000,
        "AZ-900": 8000,  "SC-900": 7000,  "AI-900": 8000,  "DP-900": 7500,
        "DP-203": 16000, "AI-102": 17000,
    }
    at_risk_n = readiness_distribution["at_risk"]
    primary_cert = team_certs[0] if team_certs else "AZ-204"
    uplift = _CERT_UPLIFT.get(primary_cert, 15000)
    monthly_cost = round(at_risk_n * uplift / 12)
    roi_summary = {
        "at_risk_headcount": at_risk_n,
        "cert": primary_cert,
        "cert_market_value_uplift_usd": uplift,
        "monthly_delay_cost_usd": monthly_cost,
        "narrative": (
            f"{at_risk_n} learner(s) are below the {primary_cert} pass threshold. "
            f"Each month of delay costs approximately ${monthly_cost:,} in unrealised "
            f"salary uplift across the team."
        ) if at_risk_n > 0 else "All tracked learners are on track — no current delay cost.",
    }

    return {
        **context,
        "summary": summary,
        "readiness_distribution": readiness_distribution,
        "capacity_conflicts": capacity_conflicts,
        "risk_areas": risk_areas,
        "peer_learning_pairs": peer_pairs,
        "manager_actions": manager_actions,
        "fabric_iq": fabric_iq,
        "roi_summary": roi_summary,
    }


def _projected_learner_snapshot(learner: LearnerProfile, evidence: dict, latest_assessment: Optional[dict]) -> dict:
    normalized_evidence = _normalise_evidence(evidence)
    pass_threshold = int((latest_assessment or {}).get("pass_threshold") or _pass_threshold_for_cert(learner.cert_target))
    if not normalized_evidence:
        return {
            "learner_id": learner.learner_id,
            "bucket": "insufficient_evidence",
            "estimated_exam_score": 0,
            "pass_threshold": pass_threshold,
            "weakest_topic": None,
            "available_study_hours_pw": round(learner.work_iq_signals.available_study_hours_per_week, 1),
            "meeting_hours_pw": round(learner.work_iq_signals.meeting_hours_per_week, 1),
            "focus_hours_pw": round(learner.work_iq_signals.focus_hours_per_week, 1),
        }

    avg_evidence = _average_evidence_score(normalized_evidence)
    weakest_topic = min(normalized_evidence, key=normalized_evidence.get)
    observed_score = (latest_assessment or {}).get("estimated_exam_score")
    modeled_score = (
        avg_evidence * 1000
        + learner.work_iq_signals.available_study_hours_per_week * 18
        + learner.work_iq_signals.focus_hours_per_week * 4
        - max(0.0, learner.work_iq_signals.meeting_hours_per_week - 18) * 11
        - (35 if learner.has_prior_failures and not (latest_assessment or {}).get("passed") else 0)
    )
    estimated_exam_score = round(
        0.55 * float(observed_score) + 0.45 * modeled_score
        if isinstance(observed_score, (int, float))
        else modeled_score
    )
    estimated_exam_score = int(_clamp(estimated_exam_score, 0, 1000))
    bucket = "on_track" if estimated_exam_score >= pass_threshold else "at_risk"

    return {
        "learner_id": learner.learner_id,
        "bucket": bucket,
        "estimated_exam_score": estimated_exam_score,
        "pass_threshold": pass_threshold,
        "weakest_topic": weakest_topic,
        "available_study_hours_pw": round(learner.work_iq_signals.available_study_hours_per_week, 1),
        "meeting_hours_pw": round(learner.work_iq_signals.meeting_hours_per_week, 1),
        "focus_hours_pw": round(learner.work_iq_signals.focus_hours_per_week, 1),
    }


def _project_team_distribution(team_id: str, learners: list[LearnerProfile], evidence_by_learner: dict[str, dict], latest_assessments: dict[str, Optional[dict]]) -> dict:
    snapshots = [
        _projected_learner_snapshot(learner, evidence_by_learner.get(learner.learner_id, {}), latest_assessments.get(learner.learner_id))
        for learner in learners
    ]
    readiness_distribution = {"on_track": 0, "at_risk": 0, "insufficient_evidence": 0}
    for snapshot in snapshots:
        readiness_distribution[snapshot["bucket"]] += 1

    high_capacity_risk_members = [
        learner.learner_id
        for learner in learners
        if learner.work_iq_signals.meeting_hours_per_week > 25
    ]

    summary = (
        f"What-if view for {team_id}: {readiness_distribution['on_track']} learner(s) on track, "
        f"{readiness_distribution['at_risk']} at risk, and "
        f"{readiness_distribution['insufficient_evidence']} with insufficient evidence."
    )

    return {
        "summary": summary,
        "readiness_distribution": readiness_distribution,
        "high_capacity_risk_members": high_capacity_risk_members,
        "learner_snapshots": snapshots,
    }


async def _build_manager_what_if_payload(team_id: str, learners: list[LearnerProfile], req: ManagerWhatIfRequest) -> dict:
    learner_map = {learner.learner_id: learner.model_copy(deep=True) for learner in learners}
    target = learner_map.get(req.target_learner_id)
    if not target:
        raise HTTPException(status_code=404, detail=f"Learner {req.target_learner_id} not found in {team_id}")

    if req.peer_mentor_id and req.peer_mentor_id not in learner_map:
        raise HTTPException(status_code=404, detail=f"Peer mentor {req.peer_mentor_id} not found in {team_id}")
    if req.peer_mentor_id == req.target_learner_id:
        raise HTTPException(status_code=400, detail="Peer mentor must differ from target learner")

    cloned_learners = list(learner_map.values())
    latest_assessments = {
        learner.learner_id: await _latest_submitted_assessment(learner.learner_id, learner.cert_target)
        for learner in learners
    }
    evidence_by_learner = {
        learner.learner_id: _normalise_evidence(_evidence_for_manager_summary(learner, latest_assessments[learner.learner_id]))
        for learner in learners
    }

    baseline = _project_team_distribution(team_id, cloned_learners, evidence_by_learner, latest_assessments)
    assumptions: list[str] = []

    if req.reduced_meeting_hours > 0:
        target.work_iq_signals.meeting_hours_per_week = _clamp(
            target.work_iq_signals.meeting_hours_per_week - req.reduced_meeting_hours,
            0,
            80,
        )
        target.work_iq_signals.available_study_hours_per_week = _clamp(
            target.work_iq_signals.available_study_hours_per_week + req.reduced_meeting_hours * 0.6,
            0,
            40,
        )
        assumptions.append(
            f"Protected {req.reduced_meeting_hours:.1f} meeting hour(s) per week for {target.learner_id}, converting part of that load into study time."
        )

    if req.protected_focus_hours > 0:
        target.work_iq_signals.focus_hours_per_week = _clamp(
            target.work_iq_signals.focus_hours_per_week + req.protected_focus_hours,
            0,
            80,
        )
        target.work_iq_signals.available_study_hours_per_week = _clamp(
            target.work_iq_signals.available_study_hours_per_week + req.protected_focus_hours * 0.75,
            0,
            40,
        )
        assumptions.append(
            f"Added {req.protected_focus_hours:.1f} protected focus hour(s) per week for {target.learner_id}."
        )

    target_evidence = dict(evidence_by_learner.get(target.learner_id, {}))
    if req.targeted_review_hours > 0 and target_evidence:
        weakest_topic = min(target_evidence, key=target_evidence.get)
        review_boost = min(0.18, req.targeted_review_hours * 0.02)
        target_evidence[weakest_topic] = _clamp(target_evidence[weakest_topic] + review_boost, 0.0, 1.0)
        assumptions.append(
            f"Targeted review improves {target.learner_id} on {weakest_topic.replace('_', ' ')} after {req.targeted_review_hours:.1f} hour(s) of remediation."
        )

    if req.peer_mentor_id and target_evidence:
        mentor_evidence = dict(evidence_by_learner.get(req.peer_mentor_id, {}))
        if mentor_evidence:
            weakest_topic = min(target_evidence, key=target_evidence.get)
            mentor_strength = mentor_evidence.get(weakest_topic, max(mentor_evidence.values(), default=0.0))
            peer_boost = max(0.05, min(0.18, (mentor_strength - target_evidence.get(weakest_topic, 0.0)) * 0.6 + 0.03 * max(req.peer_session_count, 1)))
            target_evidence[weakest_topic] = _clamp(target_evidence.get(weakest_topic, 0.0) + peer_boost, 0.0, 1.0)
            assumptions.append(
                f"{req.peer_mentor_id} coaches {target.learner_id} for {max(req.peer_session_count, 1)} session(s), improving {weakest_topic.replace('_', ' ')} confidence."
            )

    evidence_by_learner[target.learner_id] = target_evidence
    projected = _project_team_distribution(team_id, cloned_learners, evidence_by_learner, latest_assessments)

    baseline_target = next(item for item in baseline["learner_snapshots"] if item["learner_id"] == target.learner_id)
    projected_target = next(item for item in projected["learner_snapshots"] if item["learner_id"] == target.learner_id)

    deltas = {
        "on_track": projected["readiness_distribution"]["on_track"] - baseline["readiness_distribution"]["on_track"],
        "at_risk": projected["readiness_distribution"]["at_risk"] - baseline["readiness_distribution"]["at_risk"],
        "insufficient_evidence": projected["readiness_distribution"]["insufficient_evidence"] - baseline["readiness_distribution"]["insufficient_evidence"],
        "high_capacity_risk": len(projected["high_capacity_risk_members"]) - len(baseline["high_capacity_risk_members"]),
        "target_estimated_exam_score": projected_target["estimated_exam_score"] - baseline_target["estimated_exam_score"],
    }

    recommended_action = (
        f"Adopt this intervention for {target.learner_id}; the projected score improves by {deltas['target_estimated_exam_score']} points and moves the learner to {projected_target['bucket'].replace('_', ' ')}."
        if projected_target["bucket"] == "on_track" and deltas["target_estimated_exam_score"] > 0
        else f"This intervention helps but does not fully de-risk {target.learner_id}; keep remediation focused on {projected_target['weakest_topic'] or 'the weakest topic'} and schedule another mock exam."
    )

    scenario_summary = (
        f"If the manager protects time for {target.learner_id}"
        f"{f', adds {req.peer_mentor_id} as peer mentor' if req.peer_mentor_id else ''}, "
        f"the projected score moves from {baseline_target['estimated_exam_score']} to {projected_target['estimated_exam_score']}"
        f" against a threshold of {projected_target['pass_threshold']}."
    )

    return {
        "team_id": team_id,
        "scenario_summary": scenario_summary,
        "assumptions": assumptions,
        "baseline": {
            **baseline,
            "target_learner": baseline_target,
        },
        "projected": {
            **projected,
            "target_learner": projected_target,
        },
        "deltas": deltas,
        "recommended_action": recommended_action,
    }


# ── Routes ─────────────────────────────────────────────────────────────────

@app.get("/api/eval/summary")
async def eval_summary():
    """Trust & quality metrics for the UI: calibrated-model AUC, red-team scorecard,
    content-safety mode. Cheap (model is cached; red-team is 16 regex screens)."""
    from backend.evals.readiness_model import evaluate_readiness_model
    from backend.middleware.red_team import run_red_team
    from backend.middleware.content_safety import content_safety_mode
    rm = evaluate_readiness_model()
    rt = run_red_team()
    return {
        "readiness_model": {"auc_loo": rm["auc_loo"], "brier_loo": rm["brier_loo"], "n": rm["n"]},
        "red_team": {"held": rt["held"], "total": rt["total"],
                     "attack_success_rate": rt["attack_success_rate"]},
        "content_safety": content_safety_mode(),
    }


class FabricIQAskRequest(BaseModel):
    question: str


@app.post("/api/fabric-iq/ask")
async def fabric_iq_ask(body: FabricIQAskRequest, authorization: str = Header(default="")):
    """Query the Foundry agent that has the Fabric IQ tool, On-Behalf-Of the signed-in user.

    The frontend must send the user's Entra bearer token (Fabric IQ rejects service principals).
    """
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail=("Fabric IQ requires the signed-in user's Entra token "
                    "(Authorization: Bearer <token>). Service principals are not supported."),
        )
    token = authorization.split(" ", 1)[1].strip()
    question = (body.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Provide a 'question'.")
    from backend.middleware.red_team import screen_input
    verdict = screen_input(question)
    if not verdict.allowed:
        raise HTTPException(status_code=400,
                            detail=f"Request blocked by input guard ({verdict.category}).")
    import asyncio
    from backend.core.fabric_iq_agent import ask_fabric_iq
    try:
        result = await asyncio.to_thread(ask_fabric_iq, question, token)
    except RuntimeError as e:               # missing config / SDK prereq
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:                   # agent / Fabric call failure
        raise HTTPException(status_code=502, detail=f"Fabric IQ agent call failed: {e}")
    # Managed-OAuth first use → surface the consent link for the UI to open (HTTP 200).
    if result.get("consent_required"):
        return {"consent_required": True, "consent_link": result.get("consent_link"),
                "agent": get_settings().fabric_iq_agent_name}
    return {"answer": result.get("answer"), "citations": result.get("citations", []),
            "agent": get_settings().fabric_iq_agent_name}


@app.get("/health")
async def health():
    from backend.core import llm_cache
    from backend.middleware.pipeline import content_safety_mode
    from backend.core.foundry_orchestration import foundry_mode
    return {
        "status": "ok",
        "backend": s.model_backend.value,
        "storage": s.storage_backend.value,
        "iq_layers": {
            "foundry_iq": "azure" if s.foundry_iq_endpoint != "local" else "local",
            "work_iq": "synthetic",
            "fabric_iq": ("azure-sql" if (s.fabric_sql_endpoint and s.fabric_sql_database)
                          else "azure-agent" if s.fabric_iq_endpoint != "local" else "local"),
            "fabric_iq_ask": "ready" if bool(s.azure_ai_project_endpoint and s.fabric_iq_agent_name) else "unavailable",
        },
        "content_safety": content_safety_mode(),
        "llm_cache": llm_cache.stats(),
        "audio": "azure_speech" if (s.enable_audio and s.speech_key and s.speech_region) else "transcript_only",
        "foundry_agents": foundry_mode(),
        "foundry_responses_api": "enabled" if s.foundry_use_responses_api else "disabled",
        "key_vault": "configured" if s.azure_key_vault_url else "off",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/cache/stats")
async def cache_stats():
    """LLM response-cache hit/miss/entry counters (surfaced in the dashboard)."""
    from backend.core import llm_cache
    return llm_cache.stats()


@app.get("/api/learners")
async def list_learners():
    learners = _load_all_learners()
    return [
        {
            "learner_id": l.learner_id,
            "display_name": l.display_name or l.learner_id,
            "role": l.role,
            "team_id": l.team_id,
            "cert_target": l.cert_target,
            "deadline": l.deadline,
        }
        for l in learners
    ]


@app.get("/api/learners/{learner_id}")
async def get_learner(learner_id: str):
    return _load_learner(learner_id).model_dump()


@app.get("/api/teams")
async def list_teams():
    return _load_teams()


@app.post("/api/workflow/run")
async def run_workflow(req: RunWorkflowRequest):
    """Start the 8-agent pipeline for a learner. Returns run_id for SSE streaming."""
    learner = _load_learner(req.learner_id)
    if req.cert_target:
        learner.cert_target = req.cert_target

    # Treat failed in-session mock exams as prior failures so the Retrospective
    # agent runs. The seed profile only carries historical attempts; a learner who
    # has bombed a mock in-app (e.g. 35%) should still get a postmortem.
    try:
        _attempts = await storage.list_assessments(req.learner_id, learner.cert_target)
        _failed = [
            a for a in _attempts
            if a.get("submitted_at") and not a.get("passed", False)
        ]
        _failed.sort(key=lambda a: a.get("submitted_at", ""))
        _existing_dates = {pa.date for pa in learner.prior_attempts}
        for a in _failed[-2:]:  # most recent couple of failures
            date = (a.get("submitted_at") or "")[:10]
            if date and date not in _existing_dates:
                learner.prior_attempts.append(PriorAttempt(
                    date=date,
                    score=a.get("estimated_exam_score"),
                    outcome="Fail",
                    weak_areas=[],
                ))
                _existing_dates.add(date)
    except Exception:
        pass  # never block a workflow run on attempt enrichment

    run_id = str(uuid.uuid4())
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    _sse_queues[run_id] = q

    agents = build_agents(on_event=lambda evt: _broadcast(run_id, evt))
    orchestrator = WorkflowOrchestrator(
        intake_agent=agents["intake"],
        curator_agent=agents["curator"],
        planner_agent=agents["planner"],
        critic_agent=agents["critic"],
        engagement_agent=agents["engagement"],
        manager_agent=agents["manager"],
        assessment_agent=agents["assessment"],
        retrospective_agent=agents["retrospective"],
        storage=storage,
    )

    async def _run():
        from backend.core.foundry_orchestration import FoundrySession
        try:
            async with FoundrySession(run_id, learner.learner_id, learner.cert_target) as foundry:
                ctx = await orchestrator.run(
                    learner,
                    on_event=lambda evt: (_broadcast(run_id, evt), foundry.relay_event(evt)),
                    run_id=run_id,
                )
                await foundry.complete(ctx)
            foundry_thread_url = getattr(foundry, "thread_url", None)
            # Save plan to storage
            final_plan = ctx.outputs.get("final_plan")
            if final_plan:
                try:
                    plan_dict = json.loads(final_plan) if isinstance(final_plan, str) else final_plan
                    plan_dict["learner_id"] = learner.learner_id
                    saved_plan = await storage.save_plan(plan_dict)

                    from backend.mcp_server.server import ProgressSeriesInput, compute_progress_series

                    progress = await compute_progress_series.fn(ProgressSeriesInput(
                        learner_id=learner.learner_id,
                        cert_id=learner.cert_target,
                        plan_id=saved_plan["id"],
                    ))
                    _broadcast(run_id, TraceEvent(
                        event_id=str(uuid.uuid4()),
                        run_id=run_id,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        event_type=TraceEventType.TOOL_RESULT,
                        agent_name="orchestrator",
                        data={
                            "tool": "compute_progress_series",
                            "result_length": len(str(progress)),
                            "result": progress,
                        },
                    ))
                except Exception as e:
                    logger.warning("Could not save plan", error=str(e))
            # Signal completion
            complete_payload: dict = {"type": "workflow_complete", "run_id": run_id,
                                      "status": ctx.trace.final_status}
            if foundry_thread_url:
                complete_payload["foundry_thread_url"] = foundry_thread_url
            q.put_nowait(complete_payload)
        except Exception as e:
            error_message = str(e)
            if s.model_backend.value == "foundry_local" and "APIConnectionError" in error_message:
                error_message = (
                    f"Could not reach Foundry Local at {s.foundry_local_endpoint}. "
                    f"Load '{s.foundry_local_model_alias}' first, or run start.sh without --skip-model."
                )
            logger.error("Workflow failed", run_id=run_id, error=error_message)
            q.put_nowait({"type": "workflow_error", "run_id": run_id, "error": error_message})

    asyncio.create_task(_run())
    return {"run_id": run_id, "learner_id": req.learner_id, "status": "running"}


@app.get("/api/workflow/{run_id}/stream")
async def stream_events(run_id: str):
    """SSE endpoint — streams trace events for a running workflow."""
    q = _sse_queues.get(run_id)
    if not q:
        # Try to load from storage
        trace = await storage.get_trace(run_id)
        if trace:
            async def _replay():
                yield f"data: {json.dumps(trace)}\n\n"
            return StreamingResponse(_replay(), media_type="text/event-stream")
        raise HTTPException(status_code=404, detail="Run not found")

    async def _stream() -> AsyncGenerator[str, None]:
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=30)
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") in ("workflow_complete", "workflow_error"):
                    _sse_queues.pop(run_id, None)
                    break
            except asyncio.TimeoutError:
                yield ": ping\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


@app.get("/api/workflow/{run_id}/trace")
async def get_trace(run_id: str):
    trace = await storage.get_trace(run_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace


@app.get("/api/traces/{learner_id}")
async def list_traces_for_learner(learner_id: str):
    """Return all traces for a learner, newest first — used to restore run state after navigation."""
    traces = await storage.list_traces(learner_id)
    return sorted(traces, key=lambda t: t.get("started_at") or t.get("_updated_at") or "", reverse=True)


@app.get("/api/plan/{plan_id}")
async def get_plan_by_id(plan_id: str):
    """Fetch a single plan by ID — used by the frontend to restore state after navigation."""
    plan = await storage.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@app.get("/api/plans/{learner_id}")
async def get_plans(learner_id: str):
    return await storage.list_plans(learner_id)


@app.post("/api/plans/approve")
async def approve_plan(req: ApproveRequest):
    """HITL approval gate — marks a plan as approved and publishable."""
    plan = await storage.approve_plan(req.plan_id, req.approved_by)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    logger.info("Plan approved", plan_id=req.plan_id, approved_by=req.approved_by)
    return {"status": "approved", "plan_id": req.plan_id, "approved_by": req.approved_by}


@app.api_route("/api/assessment/generate", methods=["GET", "POST"])
async def generate_assessment_route(
    learner_id: str = Query(...),
    cert_id: str = Query(...),
    question_count: int = Query(default=20),
    difficulty: Optional[str] = Query(default=None),
):
    from backend.mcp_server.server import generate_assessment, AssessmentInput
    result = await generate_assessment.fn(AssessmentInput(
        learner_id=learner_id,
        cert_id=cert_id,
        question_count=question_count,
        difficulty=difficulty,
    ))
    # Persist the full assessment (incl. answer key) server-side so it can be
    # scored later, then return a client-safe copy with the answer key removed.
    await storage.save_assessment(result)
    safe = {**result, "questions": [
        {k: v for k, v in q.items() if k not in ("correct_index", "explanation")}
        for q in result.get("questions", [])
    ]}
    return safe


@app.post("/api/assessment/submit")
async def submit_assessment(req: AssessmentSubmitRequest):
    """Score an assessment and compute domain scores."""
    from backend.mcp_server.server import compute_readiness_forecast, ForecastInput
    import json
    from pathlib import Path

    cert_path = Path(s.data_dir) / "synthetic" / "cert_structures.json"
    cert_structures = json.loads(cert_path.read_text()) if cert_path.exists() else {}
    cert = cert_structures.get(req.cert_id, {})
    pass_threshold = cert.get("passing_score", 700)

    # Score against the stored answer key (never trust client-supplied keys).
    stored = await storage.get_assessment(req.assessment_id)
    if not stored:
        raise HTTPException(status_code=404, detail="Assessment not found or expired")

    answer_key = {q["question_id"]: q["correct_index"] for q in stored.get("questions", [])}
    domain_by_qid = {q["question_id"]: q.get("domain", "general") for q in stored.get("questions", [])}

    # Per-domain correctness → grounds the readiness forecast in real evidence.
    domain_totals: dict[str, int] = {}
    domain_correct: dict[str, int] = {}
    correct = 0
    for q_id, ans in req.answers.items():
        if q_id not in answer_key:
            continue
        dom = domain_by_qid.get(q_id, "general")
        domain_totals[dom] = domain_totals.get(dom, 0) + 1
        if ans == answer_key[q_id]:
            correct += 1
            domain_correct[dom] = domain_correct.get(dom, 0) + 1

    total = len([q for q in req.answers if q in answer_key])
    score_pct = (correct / max(total, 1)) * 100
    estimated_score = int(score_pct * 10)

    evidence = {
        dom: round(domain_correct.get(dom, 0) / domain_totals[dom], 3)
        for dom in domain_totals
    } or {"general": score_pct / 100}
    forecast = await compute_readiness_forecast.fn(ForecastInput(
        learner_id=req.learner_id,
        cert_id=req.cert_id,
        plan_id="adhoc",
        evidence_json=json.dumps(evidence),
        observed_exam_score=estimated_score,
        observed_score_pct=round(score_pct, 1),
    ))

    stored["submitted_at"] = datetime.now(timezone.utc).isoformat()
    stored["submitted_answers"] = req.answers
    stored["evidence"] = evidence
    stored["score_pct"] = round(score_pct, 1)
    stored["questions_scored"] = total
    stored["estimated_exam_score"] = estimated_score
    stored["pass_threshold"] = pass_threshold
    stored["passed"] = estimated_score >= pass_threshold
    stored["forecast"] = forecast
    await storage.save_assessment(stored)

    # Auto-trigger manager intervention after 2 consecutive NOT YET verdicts.
    if not stored["passed"]:
        recent = await storage.list_assessments(req.learner_id, req.cert_id)
        submitted_sorted = sorted(
            [a for a in recent if a.get("submitted_at") and "passed" in a],
            key=lambda a: a.get("submitted_at", ""), reverse=True,
        )
        if len(submitted_sorted) >= 2 and not submitted_sorted[1].get("passed"):
            try:
                learner_obj = _load_learner(req.learner_id)
                team_id_auto = learner_obj.team_id
                import uuid as _uuid_mod
                await storage.save_manager_intervention({
                    "id": str(_uuid_mod.uuid4()),
                    "team_id": team_id_auto,
                    "learner_id": req.learner_id,
                    "priority": "high",
                    "reasons": [
                        f"{req.learner_id} scored below the {pass_threshold} pass threshold in 2 consecutive {req.cert_id} assessments.",
                        f"Latest score: {estimated_score} (threshold: {pass_threshold}). Prior attempt also below threshold.",
                        "Recommend immediate manager check-in and study plan review.",
                    ],
                    "owner_id": team_id_auto,
                    "status": "open",
                    "manager_note": (
                        f"Auto-triggered: {req.learner_id} missed the {req.cert_id} pass threshold twice in a row. "
                        "Review capacity signals and consider protecting study blocks."
                    ),
                    "trigger": "consecutive_not_yet",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
            except Exception:
                pass  # never block the assessment response for an intervention write failure

    from backend.evals.readiness_model import booking_verdict as _bv
    passed = estimated_score >= pass_threshold
    bv = _bv("ready" if passed else "not_ready",
              float(forecast.get("pass_probability", 0.0)) if isinstance(forecast, dict) else 0.0)

    return {
        "assessment_id": req.assessment_id,
        "learner_id": req.learner_id,
        "score_pct": round(score_pct, 1),
        "questions_scored": total,
        "estimated_exam_score": estimated_score,
        "pass_threshold": pass_threshold,
        "passed": passed,
        "booking_verdict": bv,
        "forecast": forecast,
        "ai_disclosure": "AI-generated assessment result",
    }


async def _latest_submitted_assessment(learner_id: str, cert_id: str) -> Optional[dict]:
    assessments = await storage.list_assessments(learner_id, cert_id)
    submitted = [assessment for assessment in assessments if assessment.get("submitted_at") and isinstance(assessment.get("evidence"), dict)]
    if not submitted:
        return None

    submitted.sort(key=lambda assessment: assessment.get("submitted_at", ""), reverse=True)
    return submitted[0]


async def _latest_assessment_evidence(learner_id: str, cert_id: str) -> dict:
    latest = await _latest_submitted_assessment(learner_id, cert_id)
    if not latest:
        return {}
    return latest.get("evidence", {})


async def _latest_plan(learner_id: str, cert_id: str) -> Optional[dict]:
    plans = await storage.list_plans(learner_id, cert_id)
    if not plans:
        return None

    def _plan_sort_key(plan: dict) -> tuple[int, str]:
        status_rank = 1 if plan.get("status") == "approved" else 0
        timestamp = str(
            plan.get("approved_at")
            or plan.get("_updated_at")
            or plan.get("created_at")
            or ""
        )
        return (status_rank, timestamp)

    plans.sort(key=_plan_sort_key, reverse=True)
    return plans[0]


@app.get("/api/progress/{learner_id}/{cert_id}")
async def get_progress(learner_id: str, cert_id: str):
    from backend.mcp_server.server import ProgressSeriesInput, compute_progress_series

    plan = await _latest_plan(learner_id, cert_id)
    progress_payload = {
        "learner_id": learner_id,
        "cert_id": cert_id,
        "plan_id": plan.get("id") if plan else "latest",
        "series": [],
    }
    if plan:
        progress_payload = await compute_progress_series.fn(ProgressSeriesInput(
            learner_id=learner_id,
            cert_id=cert_id,
            plan_id=plan["id"],
        ))

    assessments = await storage.list_assessments(learner_id, cert_id)
    submitted = [assessment for assessment in assessments if assessment.get("submitted_at")]
    submitted.sort(key=lambda assessment: assessment.get("submitted_at", ""))

    attempts = []
    for index, assessment in enumerate(submitted, start=1):
        questions = assessment.get("questions", [])
        difficulties = {q.get("difficulty") for q in questions if q.get("difficulty")}
        if len(difficulties) == 1:
            difficulty = next(iter(difficulties))
        elif difficulties:
            difficulty = "Mixed"
        else:
            difficulty = "Unknown"

        attempts.append({
            "attempt_number": index,
            "assessment_id": assessment.get("assessment_id") or assessment.get("id"),
            "submitted_at": assessment.get("submitted_at"),
            "score_pct": assessment.get("score_pct"),
            "estimated_exam_score": assessment.get("estimated_exam_score"),
            "passed": assessment.get("passed", False),
            "difficulty": difficulty,
            "question_count": len(questions),
        })

    return {**progress_payload, "attempts": attempts}


@app.get("/api/mastery/{learner_id}/{cert_id}")
async def get_mastery(learner_id: str, cert_id: str):
    from backend.mcp_server.server import compute_domain_mastery, DomainMasteryInput
    import json
    from pathlib import Path

    path = Path(s.data_dir) / "synthetic" / "learners.json"
    learners = json.loads(path.read_text())
    learner = next((l for l in learners if l["learner_id"] == learner_id), None)
    evidence = await _latest_assessment_evidence(learner_id, cert_id)
    if not evidence:
        evidence = learner.get("prior_assessment_evidence", {}) if learner else {}

    return await compute_domain_mastery.fn(DomainMasteryInput(
        learner_id=learner_id,
        cert_id=cert_id,
        evidence_json=json.dumps(evidence),
    ))


@app.get("/api/forecast/{learner_id}/{cert_id}")
async def get_forecast(learner_id: str, cert_id: str):
    from backend.mcp_server.server import compute_readiness_forecast, ForecastInput
    import json
    from pathlib import Path

    path = Path(s.data_dir) / "synthetic" / "learners.json"
    learners = json.loads(path.read_text())
    learner = next((l for l in learners if l["learner_id"] == learner_id), None)
    latest_assessment = await _latest_submitted_assessment(learner_id, cert_id)
    evidence = latest_assessment.get("evidence", {}) if latest_assessment else {}
    if not evidence:
        evidence = learner.get("prior_assessment_evidence", {}) if learner else {}

    forecast = await compute_readiness_forecast.fn(ForecastInput(
        learner_id=learner_id,
        cert_id=cert_id,
        plan_id="latest",
        evidence_json=json.dumps(evidence),
        observed_exam_score=latest_assessment.get("estimated_exam_score") if latest_assessment else None,
        observed_score_pct=latest_assessment.get("score_pct") if latest_assessment else None,
    ))
    # Calibrated P(pass) from the trained readiness model (the headline-metric model;
    # LOO AUC ≈ 0.80). Abstains (INSUFFICIENT) if the learner's signals are missing.
    try:
        from backend.evals.readiness_model import predict_pass_probability
        sig = (learner or {}).get("work_iq_signals", {}) or {}
        practice = (latest_assessment or {}).get("score_pct")
        if practice is None and isinstance(forecast, dict) and forecast.get("estimated_exam_score"):
            practice = forecast["estimated_exam_score"] / 10.0   # 0-1000 → 0-100
        if isinstance(forecast, dict):
            forecast["calibrated"] = predict_pass_probability(
                practice_score=practice,
                hours_studied=sig.get("available_study_hours_per_week") or sig.get("focus_hours_per_week"),
                meeting_hours_pw=sig.get("meeting_hours_per_week"),
            )
    except Exception:
        pass
    return forecast


@app.get("/api/reports/learner/{learner_id}/{cert_id}.pdf")
async def learner_report_pdf(learner_id: str, cert_id: str):
    """Download a learner readiness PDF (forecast + domain mastery + plan summary)."""
    from backend.reports.pdf import generate_learner_report, cached_pdf

    learner = _load_learner(learner_id)  # 404s if unknown
    forecast = await get_forecast(learner_id, cert_id)
    mastery = await get_mastery(learner_id, cert_id)
    plans = await storage.list_plans(learner_id, cert_id)
    plan = plans[-1] if plans else None

    pdf = cached_pdf(
        learner_id, f"learner_{cert_id}",
        generate_learner_report, learner.model_dump(mode="json"), forecast, mastery, plan,
    )
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="readiness_{learner_id}_{cert_id}.pdf"'},
    )


@app.get("/api/reports/manager/{team_id}.pdf")
async def manager_brief_pdf(team_id: str):
    """Download a manager handoff brief PDF (readiness, risk, Fabric IQ gaps, pinned actions)."""
    from backend.reports.pdf import generate_manager_brief, cached_pdf

    team_learners = [l for l in _load_all_learners() if l.team_id == team_id]
    if not team_learners:
        raise HTTPException(status_code=404, detail=f"Team {team_id} not found")
    insights = await _build_manager_insight_payload(team_id, team_learners)
    interventions = await storage.list_manager_interventions(team_id)
    peer_sessions = await storage.list_peer_learning_sessions(team_id)

    pdf = cached_pdf(
        team_id, "manager_brief",
        generate_manager_brief, team_id, insights, interventions, peer_sessions,
    )
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="manager_brief_{team_id}.pdf"'},
    )


# ── Audio study briefing / concept podcast (grounded, two-host) ─────────────

def _resolve_focus_domain(cert_id: str, evidence: dict, focus: Optional[str]):
    """Pick which concept to teach.

    focus None/"weakest" → the learner's highest-leverage gap (or top-weight domain).
    focus "overview"     → no single domain (multi-domain overview briefing).
    focus <id/name/svc>  → the matching domain (learner's choice).
    Returns (domain_dict | None, is_weakest, mode).
    """
    from backend.iq.fabric_iq import get_fabric_iq
    fiq = get_fabric_iq()
    domains = fiq.get_domain_thresholds(cert_id)
    f = (focus or "").strip().lower()

    if f == "overview":
        return None, False, "overview"

    if f and f not in ("weakest", "auto"):
        for d in domains:
            haystack = (d["domain_id"] + " " + d["name"] + " " + " ".join(d.get("services", []))).lower()
            if f in d["domain_id"].lower() or f in d["name"].lower() or f in haystack:
                return d, False, "concept"
        # no match → fall through to weakest

    sem = fiq.get_readiness_semantics(cert_id, evidence)
    gap = None if sem.get("insufficient_evidence") else sem.get("highest_leverage_gap")
    if gap:
        for d in domains:
            if d["name"] == gap["name"]:
                return d, True, "concept"
    if domains:
        return max(domains, key=lambda d: d.get("weight_pct", 0)), True, "concept"
    return None, False, "overview"


async def _build_audio_context(learner_id: str, cert_id: str, focus: Optional[str] = None):
    """Gather grounded material for the podcast: weighted domains (Fabric IQ), the
    readiness forecast, the focus concept, and cited excerpts (Foundry IQ)."""
    from backend.iq.fabric_iq import get_fabric_iq
    from backend.iq.foundry_iq import get_foundry_iq

    learner = _load_learner(learner_id)  # 404s if unknown
    thresholds = get_fabric_iq().get_domain_thresholds(cert_id)
    forecast = await get_forecast(learner_id, cert_id)
    latest = await _latest_submitted_assessment(learner_id, cert_id)
    evidence = _normalise_evidence(_evidence_for_manager_summary(learner, latest))
    focus_domain, is_weakest, mode = _resolve_focus_domain(cert_id, evidence, focus)

    if mode == "concept" and focus_domain:
        query = f"{cert_id} {focus_domain['name']} {' '.join(focus_domain.get('services', [])[:3])}"
    else:
        query = f"{cert_id} key topics by domain"
    results = await get_foundry_iq().search(query, top_k=3)
    excerpts = [{"title": r.title, "excerpt": r.excerpt} for r in results]
    return {
        "learner_obj": learner, "learner_id": learner_id, "cert_id": cert_id,
        "domains": thresholds, "forecast": forecast, "excerpts": excerpts,
        "focus_domain": focus_domain, "is_weakest": is_weakest, "mode": mode,
    }


def _audio_user_message(ctx: dict) -> str:
    excerpts = "\n".join(f"- {e['title']}: {e['excerpt'][:220]}" for e in ctx["excerpts"])
    if ctx["mode"] == "concept" and ctx["focus_domain"]:
        d = ctx["focus_domain"]
        why = ("This is the learner's weakest / highest-leverage area."
               if ctx["is_weakest"] else "The learner chose this concept to study.")
        return (
            f"Certification: {ctx['cert_id']}\nLearner: {ctx['learner_id']}\n"
            f"DEEP-TEACH this ONE concept as a focused podcast episode: "
            f"{d['name']} ({d['weight_pct']}% of the exam).\n"
            f"Key services: {', '.join(d.get('services', []))}.\n{why}\n"
            f"Approved source excerpts:\n{excerpts}\n\n"
            "Teach it thoroughly and conversationally: what it is, why it matters for the "
            "exam, the key services, a concrete worked scenario, a common mistake to avoid, "
            "and end with ONE self-check question. Return PodcastScript JSON grounded only "
            "in the material above."
        )
    domains = "; ".join(
        f"{d['name']} ({d['weight_pct']}%) services: {', '.join(d.get('services', [])[:3])}"
        for d in ctx["domains"]
    )
    weak = ctx["forecast"].get("weakest_topic", "")
    return (
        f"Certification: {ctx['cert_id']}\nLearner: {ctx['learner_id']}\n"
        f"Weighted domains: {domains}\n"
        f"Weakest area (from readiness forecast): {weak or 'unknown'}\n"
        f"Approved source excerpts:\n{excerpts}\n\n"
        "Write the two-host audio study briefing as PodcastScript JSON, grounded only in "
        "the material above."
    )


# Per-key locks for script generation (in-memory is fine; lock lifetime = process).
_audio_script_locks: dict[tuple, asyncio.Lock] = {}


def _script_cache_path(learner_id: str, cert_id: str, focus: str) -> Path:
    import hashlib
    slug = hashlib.sha256(f"{learner_id}|{cert_id}|{focus}".encode()).hexdigest()[:16]
    d = Path(get_settings().store_dir) / "audio_scripts"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{slug}.json"


async def _generate_audio_script(learner_id: str, cert_id: str, focus: Optional[str] = None) -> dict:
    from backend.agents.factory import build_audio_agent
    from backend.agents.fallbacks import build_fallback

    norm_focus = (focus or "").strip().lower()
    lock_key = (learner_id, cert_id, norm_focus)
    cache_path = _script_cache_path(learner_id, cert_id, norm_focus)

    # Fast path: script already on disk — survives backend restarts.
    if cache_path.exists():
        return json.loads(cache_path.read_text())

    # Per-key lock prevents duplicate generation under concurrent requests.
    if lock_key not in _audio_script_locks:
        _audio_script_locks[lock_key] = asyncio.Lock()
    async with _audio_script_locks[lock_key]:
        if cache_path.exists():  # re-check after acquiring lock
            return json.loads(cache_path.read_text())

        ctx = await _build_audio_context(learner_id, cert_id, focus)
        agent = build_audio_agent()
        result = await agent.run(messages=[{"role": "user", "content": _audio_user_message(ctx)}], context=ctx)
        payload = result.parsed.model_dump(mode="json") if result.parsed is not None else None
        if not payload or not payload.get("turns"):
            payload = await build_fallback("audio_curriculum", ctx)
        if isinstance(payload, dict):
            payload["mode"] = ctx["mode"]
            payload["focus"] = (ctx["focus_domain"] or {}).get("name", "") if ctx["focus_domain"] else "overview"
            payload["is_weakest"] = ctx["is_weakest"]

        # Persist to disk so transcript and MP3 always use the same script
        # even if the backend restarts between the two requests.
        cache_path.write_text(json.dumps(payload))
        return payload


@app.get("/api/audio/concepts/{learner_id}/{cert_id}")
async def audio_concepts(learner_id: str, cert_id: str):
    """List concepts the learner can pick for a podcast, flagging the weakest (recommended)."""
    from backend.iq.fabric_iq import get_fabric_iq
    from backend.mcp_server.server import compute_domain_mastery, DomainMasteryInput

    learner = _load_learner(learner_id)
    domains = get_fabric_iq().get_domain_thresholds(cert_id)
    latest = await _latest_submitted_assessment(learner_id, cert_id)
    evidence = _normalise_evidence(_evidence_for_manager_summary(learner, latest))
    focus_domain, _, _ = _resolve_focus_domain(cert_id, evidence, None)
    weakest_id = (focus_domain or {}).get("domain_id", "")

    mastery = await compute_domain_mastery.fn(DomainMasteryInput(
        learner_id=learner_id, cert_id=cert_id, evidence_json=json.dumps(evidence)))
    mastery_by_id = {d["domain_id"]: d.get("mastery_pct") for d in mastery.get("domains", [])}

    concepts = [{
        "domain_id": d["domain_id"], "name": d["name"], "weight_pct": d["weight_pct"],
        "services": d.get("services", []), "mastery_pct": mastery_by_id.get(d["domain_id"]),
        "is_weakest": d["domain_id"] == weakest_id,
    } for d in domains]
    return {"cert_id": cert_id, "weakest_domain_id": weakest_id, "concepts": concepts}


@app.get("/api/audio/learner/{learner_id}/{cert_id}/transcript")
async def audio_transcript(learner_id: str, cert_id: str, focus: Optional[str] = Query(None)):
    """Grounded podcast transcript + citations (works without a Speech key).

    `focus` selects the concept: omitted/"weakest" → teach the weakest area;
    "overview" → multi-domain briefing; a domain id/name/service → teach that concept.
    """
    from backend.audio.podcast import is_configured
    script = await _generate_audio_script(learner_id, cert_id, focus)
    return {"script": script, "audio_available": is_configured()}


@app.get("/api/audio/learner/{learner_id}/{cert_id}.mp3")
async def audio_mp3(learner_id: str, cert_id: str, focus: Optional[str] = Query(None)):
    """Synthesize the podcast to MP3 via Azure AI Speech (503 if not configured)."""
    from backend.audio.podcast import synthesize_script, AudioNotConfigured
    from backend.models import PodcastScript

    script = await _generate_audio_script(learner_id, cert_id, focus)
    try:
        audio = await synthesize_script(PodcastScript.model_validate(script), cache_key=learner_id)
    except AudioNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))
    return Response(
        content=audio, media_type="audio/mpeg",
        headers={"Content-Disposition": f'inline; filename="podcast_{learner_id}_{cert_id}.mp3"'},
    )


@app.get("/api/manager/{team_id}/insights")
async def manager_insights(team_id: str):
    """Return team-level manager insights using Work IQ signals and recent assessment state."""
    all_learners = _load_all_learners()
    team_learners = [l for l in all_learners if l.team_id == team_id]
    if not team_learners:
        raise HTTPException(status_code=404, detail=f"Team {team_id} not found")
    return await _build_manager_insight_payload(team_id, team_learners)


@app.post("/api/manager/{team_id}/what-if")
async def manager_what_if(team_id: str, req: ManagerWhatIfRequest):
    team_learners = [learner for learner in _load_all_learners() if learner.team_id == team_id]
    if not team_learners:
        raise HTTPException(status_code=404, detail=f"Team {team_id} not found")
    return await _build_manager_what_if_payload(team_id, team_learners, req)


@app.get("/api/manager/{team_id}/peer-sessions")
async def list_peer_learning_sessions(team_id: str):
    sessions = await storage.list_peer_learning_sessions(team_id)
    sessions.sort(key=lambda session: str(session.get("_updated_at") or session.get("created_at") or ""), reverse=True)
    return sessions


@app.post("/api/manager/{team_id}/peer-sessions")
async def save_peer_learning_session(team_id: str, req: PeerLearningSessionRequest):
    existing_sessions = await storage.list_peer_learning_sessions(team_id)
    existing = next((item for item in existing_sessions if item.get("id") == req.id), None)
    session = await storage.save_peer_learning_session({
        "id": req.id,
        "team_id": team_id,
        "mentor_id": req.mentor_id,
        "learner_id": req.learner_id,
        "cert_id": req.cert_id,
        "focus_domain": req.focus_domain,
        "suggested_slot": req.suggested_slot,
        "rationale": req.rationale,
        "owner_id": req.owner_id,
        "status": req.status,
        "manager_note": req.manager_note,
        "created_at": (existing or {}).get("created_at") or datetime.now(timezone.utc).isoformat(),
    })
    return session


@app.delete("/api/manager/{team_id}/peer-sessions/{session_id}")
async def delete_peer_learning_session(team_id: str, session_id: str):
    sessions = await storage.list_peer_learning_sessions(team_id)
    session = next((item for item in sessions if item.get("id") == session_id), None)
    if not session:
        raise HTTPException(status_code=404, detail="Peer learning session not found")

    deleted = await storage.delete_peer_learning_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Peer learning session not found")
    return {"status": "deleted", "id": session_id}


@app.get("/api/manager/{team_id}/interventions")
async def list_manager_interventions(team_id: str):
    interventions = await storage.list_manager_interventions(team_id)
    interventions.sort(key=lambda item: str(item.get("_updated_at") or item.get("created_at") or ""), reverse=True)
    return interventions


@app.post("/api/manager/{team_id}/interventions")
async def save_manager_intervention(team_id: str, req: ManagerInterventionRequest):
    existing_interventions = await storage.list_manager_interventions(team_id)
    existing = next((item for item in existing_interventions if item.get("id") == req.id), None)
    intervention = await storage.save_manager_intervention({
        "id": req.id,
        "team_id": team_id,
        "learner_id": req.learner_id,
        "priority": req.priority,
        "reasons": req.reasons,
        "owner_id": req.owner_id,
        "status": req.status,
        "manager_note": req.manager_note,
        "created_at": (existing or {}).get("created_at") or datetime.now(timezone.utc).isoformat(),
    })
    return intervention


@app.delete("/api/manager/{team_id}/interventions/{intervention_id}")
async def delete_manager_intervention(team_id: str, intervention_id: str):
    interventions = await storage.list_manager_interventions(team_id)
    intervention = next((item for item in interventions if item.get("id") == intervention_id), None)
    if not intervention:
        raise HTTPException(status_code=404, detail="Manager intervention not found")

    deleted = await storage.delete_manager_intervention(intervention_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Manager intervention not found")
    return {"status": "deleted", "id": intervention_id}


@app.get("/api/cert-structures/{cert_id}")
async def get_cert_structure(cert_id: str):
    import json
    from pathlib import Path
    path = Path(s.data_dir) / "synthetic" / "cert_structures.json"
    structures = json.loads(path.read_text())
    if cert_id not in structures:
        raise HTTPException(status_code=404, detail=f"Cert {cert_id} not found")
    return structures[cert_id]


# ── Evaluation & RAI endpoints ─────────────────────────────────────────────

@app.get("/api/evals/groundedness/{run_id}")
async def get_groundedness_eval(run_id: str):
    """
    Return the groundedness evaluation for a completed workflow run.
    Uses azure-ai-evaluation SDK when MODEL_BACKEND=azure_foundry, otherwise
    falls back to the fast heuristic evaluator.
    """
    from backend.evals.groundedness import evaluate_async, get_eval_model_config

    trace = await storage.get_trace(run_id)
    if not trace:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    # Collect curator and critic outputs — the most citation-heavy agents
    citation_agents = {"curator", "readiness_critic"}
    outputs: list[str] = []
    for evt in (trace.get("events") or []):
        if not isinstance(evt, dict):
            continue
        if evt.get("agent_name") not in citation_agents:
            continue
        data = evt.get("data") or {}
        if evt.get("event_type") in ("tool_result", "agent_complete", "agent_output"):
            result = data.get("result") or data.get("structured_output") or data.get("output") or ""
            text = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
            if text and len(text) > 10:
                outputs.append(text[:2000])  # cap per-agent to keep context manageable

    combined = " ".join(outputs) if outputs else json.dumps(trace)[:4000]
    model_config = get_eval_model_config()

    import asyncio as _asyncio
    try:
        result = await _asyncio.wait_for(
            evaluate_async(combined, model_config=model_config),
            timeout=25.0,
        )
    except _asyncio.TimeoutError:
        from backend.evals.groundedness import _heuristic_evaluate
        result = _heuristic_evaluate(combined, threshold=0.90)
        result.evaluator = "heuristic_timeout_fallback"

    return {
        "run_id": run_id,
        "groundedness_score": result.score,
        "passed": result.passed,
        "citation_count": result.citation_count,
        "assertion_count": result.assertion_count,
        "uncited_sample": result.uncited_assertions[:3],
        "evaluator": result.evaluator,
        "note": (
            "Evaluated using Azure AI Evaluation SDK (LLM judge)"
            if result.evaluator == "azure_ai_evaluation"
            else "Evaluated using heuristic citation-coverage score (LLM judge timed out or not configured)"
        ),
    }


@app.get("/api/evals/rubric/{run_id}")
async def get_rubric_eval(run_id: str):
    """
    Run deterministic rubric checks (C1–C4, P1–P5, CR1–CR4, A1–A4, E1–E3, M1–M4, R1–R4)
    against all stored agent outputs for a workflow run.
    """
    from backend.evals.agent_rubrics import batch_evaluate

    trace = await storage.get_trace(run_id)
    if not trace:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    # Gather agent outputs from trace events
    samples: dict = {}
    agent_map = {
        "curator": "curator",
        "plan_generator": "plan_generator",
        "readiness_critic": "readiness_critic",
        "assessment": "assessment",
        "engagement": "engagement",
        "manager_insights": "manager_insights",
        "retrospective": "retrospective",
    }
    for evt in (trace.get("events") or []):
        if not isinstance(evt, dict):
            continue
        agent = evt.get("agent_name", "")
        if agent not in agent_map:
            continue
        event_type = evt.get("event_type", "")
        if event_type not in ("tool_result", "agent_complete", "agent_output"):
            continue
        data = evt.get("data", {})
        # agent_complete events carry structured_output; tool_result events carry result
        payload = data.get("result") or data.get("structured_output")
        if payload is not None:
            samples.setdefault(agent_map[agent], payload)

    return batch_evaluate({k: v for k, v in samples.items() if v is not None})


@app.get("/api/rai/status")
async def get_rai_status():
    """
    Return the current Responsible AI configuration — which controls are active,
    their mode (Azure / local), and their effective settings.
    Surfaced in the frontend Safety tab so judges can inspect the RAI posture at a glance.
    """
    content_safety_mode = (
        "azure_ai_content_safety"
        if s.azure_content_safety_endpoint and s.azure_content_safety_key
        else "regex_fallback"
    )
    eval_mode = (
        "azure_ai_evaluation"
        if s.model_backend.value == "azure_foundry" and s.azure_ai_project_endpoint
        else "heuristic"
    )
    foundry_orchestration = (
        "azure_ai_foundry_agent_service"
        if s.model_backend.value == "azure_foundry" and s.azure_ai_project_endpoint
        else "custom_orchestrator_local"
    )
    return {
        "rai_controls": [
            {
                "control": "Content Safety",
                "mode": content_safety_mode,
                "active": True,
                "detail": (
                    f"Azure AI Content Safety (severity threshold {s.azure_content_safety_threshold})"
                    if content_safety_mode == "azure_ai_content_safety"
                    else "Regex guardrail (blocklist: jailbreak, self-harm, violence patterns)"
                ),
                "categories": ["Hate", "SelfHarm", "Sexual", "Violence"],
            },
            {
                "control": "PII Redaction",
                "mode": "domain_aware",
                "active": True,
                "detail": (
                    "Unconditional redaction of emails and phone numbers. "
                    "Conditional redaction of names using a cert/role domain vocabulary to preserve technical terms."
                ),
            },
            {
                "control": "Citation Gate",
                "mode": "pipeline_check",
                "active": True,
                "detail": "Flags agent outputs that lack citation markers. Applied to Curator, Assessment, and Critic agents.",
            },
            {
                "control": "Bias Audit",
                "mode": "regex_scan",
                "active": True,
                "detail": "Scans for gendered pronouns and role-stereotype patterns. Logs findings; does not block.",
            },
            {
                "control": "Groundedness Evaluation",
                "mode": eval_mode,
                "active": True,
                "detail": (
                    "LLM-as-judge via azure-ai-evaluation SDK (GroundednessEvaluator)"
                    if eval_mode == "azure_ai_evaluation"
                    else "Heuristic citation-coverage score. Set MODEL_BACKEND=azure_foundry to enable LLM judge."
                ),
            },
            {
                "control": "HITL Approval Gate",
                "mode": "human_in_the_loop",
                "active": True,
                "detail": "Study plans remain in 'draft' status until a human approves via /api/plans/approve.",
            },
            {
                "control": "Foundry Agent Orchestration",
                "mode": foundry_orchestration,
                "active": True,
                "detail": (
                    "Workflow runs are registered and tracked as Azure AI Foundry Agent threads."
                    if foundry_orchestration == "azure_ai_foundry_agent_service"
                    else "Custom orchestrator (local mode). Set MODEL_BACKEND=azure_foundry for Foundry Agent Service tracking."
                ),
            },
        ],
        "ai_disclosure": "EnterpriseCertIQ applies Responsible AI controls at every stage. All outputs are AI-generated and require human review before use in employment or performance decisions.",
        "model_backend": s.model_backend.value,
        "content_safety_threshold": s.azure_content_safety_threshold,
    }
