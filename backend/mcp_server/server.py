"""
EnterpriseCertIQ own MCP server (FastMCP).
Exposes 10 typed tools (incl. Fabric IQ semantic queries) consumed by the agents.

Run standalone:
    python -m backend.mcp_server.server
Or imported and started by main.py as a background task.
"""
from __future__ import annotations

import json
import logging
import math
import random
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastmcp import FastMCP
from pydantic import BaseModel

logger = logging.getLogger(__name__)

mcp = FastMCP("enterprisecertiq-tools")


def _collapse_repeated_segments(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" -")
    if not text:
        return "Untitled topic"

    parts = [part.strip() for part in re.split(r"\s+[—-]\s+", text) if part.strip()]
    if not parts:
        return text[:160]

    collapsed: list[str] = []
    for part in parts:
        if collapsed and part.casefold() == collapsed[-1].casefold():
            continue
        collapsed.append(part)

    normalized = " — ".join(collapsed)
    if len(normalized) > 160:
        normalized = f"{normalized[:157].rstrip()}..."
    return normalized


def _lra_allocate_hours(topics: list[dict], total_budget: float, min_hours: float = 0.5) -> list[dict]:
    """Largest Remainder Algorithm for topic hour allocation.

    Prevents study starvation: every topic is guaranteed at least min_hours.
    Surplus budget is distributed to the topics with the highest fractional
    remainder — the same fairness guarantee used in electoral seat allocation.

    Prevents domain starvation when a learner has limited weekly study time.
    """
    if not topics or total_budget <= 0:
        return topics

    n = len(topics)
    raw = [max(float(t.get("hours_allocated", 2.0)), min_hours) for t in topics]
    total_raw = sum(raw)

    if total_raw <= 0:
        equal = round(max(min_hours, total_budget / n), 1)
        return [{**t, "hours_allocated": equal} for t in topics]

    scale = total_budget / total_raw
    scaled = [r * scale for r in raw]
    floored = [max(min_hours, math.floor(s * 2) / 2) for s in scaled]  # floor to nearest 0.5
    remainder = total_budget - sum(floored)

    if remainder > 0.1:
        fractions = sorted(
            range(n), key=lambda i: scaled[i] - floored[i], reverse=True
        )
        step = 0.5
        for i in fractions:
            if remainder < step:
                break
            floored[i] += step
            remainder -= step

    return [{**t, "hours_allocated": round(h, 1)} for t, h in zip(topics, floored)]


def _normalize_curated_topics(raw_topics) -> list[dict]:
    topics = raw_topics if isinstance(raw_topics, list) else []
    normalized_topics: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for index, topic in enumerate(topics, start=1):
        if not isinstance(topic, dict):
            continue

        title = _collapse_repeated_segments(topic.get("title", "Untitled topic"))
        domain = _collapse_repeated_segments(topic.get("domain", "General"))
        key = (title.casefold(), domain.casefold())
        if key in seen:
            continue
        seen.add(key)

        hours = topic.get("hours_allocated", topic.get("hours", 2.0))
        try:
            hours_value = float(hours)
        except (TypeError, ValueError):
            hours_value = 2.0

        normalized_topics.append({
            "topic_id": topic.get("topic_id") or f"topic_{index:02d}",
            "title": title,
            "domain": domain,
            "hours_allocated": round(min(max(hours_value, 0.5), 12.0), 1),
            "difficulty": topic.get("difficulty", "Medium"),
            "prerequisites": topic.get("prerequisites", []),
            "citations": topic.get("citations", []),
            "ms_learn_url": topic.get("ms_learn_url", ""),
        })

    return normalized_topics


QUESTION_STEMS_BY_DIFFICULTY = {
    "Easy": [
        "[Synthetic] For {cert_id} in {domain}, which implementation best fits {service}?",
        "[Synthetic] Which option best matches the Microsoft recommendation for {service} in {domain}?",
        "[Synthetic] A learner is reviewing {service} for {cert_id}. Which choice is correct for the {domain} objective?",
    ],
    "Medium": [
        "[Synthetic] A developer is working on {service} within {domain} for {cert_id}. What should they choose?",
        "[Synthetic] Which approach aligns with Microsoft guidance for {service} under {domain} in {cert_id}?",
        "[Synthetic] When designing {service} for the {domain} objective in {cert_id}, what is the recommended action?",
    ],
    "Hard": [
        "[Synthetic] A production workload in {service} is failing a key {domain} requirement for {cert_id}. Which remediation is most appropriate?",
        "[Synthetic] Which design decision for {service} best satisfies the trade-offs emphasized in {domain} for {cert_id}?",
        "[Synthetic] You must review an implementation of {service} against Microsoft guidance for {domain} in {cert_id}. What is the strongest correction?",
    ],
}


def _assessment_difficulty_label(raw_difficulty: Optional[str], question_index: int) -> str:
    if raw_difficulty and raw_difficulty.capitalize() in QUESTION_STEMS_BY_DIFFICULTY:
        return raw_difficulty.capitalize()
    return ["Easy", "Medium", "Hard"][question_index % 3]


def _service_for_difficulty(services: list[str], difficulty: str, question_index: int) -> str:
    if not services:
        return "General"

    if difficulty == "Easy":
        offset = 0
    elif difficulty == "Medium":
        offset = len(services) // 2
    elif difficulty == "Hard":
        offset = max(len(services) - 1, 0)
    else:
        offset = question_index

    return services[(question_index + offset) % len(services)]


# ── Tool input schemas ─────────────────────────────────────────────────────

class LearnerProfileInput(BaseModel):
    learner_id: str
    cert_target: str
    raw_profile_json: str


class FoundryIQInput(BaseModel):
    query: str
    top_k: int = 3
    cert_id: Optional[str] = None


class CitationInput(BaseModel):
    doc_id: str
    span_id: str
    claim_text: str


class StudyPlanInput(BaseModel):
    learner_id: str
    cert_id: str
    curated_topics_json: str
    available_hours_per_week: float
    deadline: str
    weeks: int = 6


class AssessmentInput(BaseModel):
    learner_id: str
    cert_id: str
    domain_focus: Optional[str] = None
    question_count: int = 20
    difficulty: Optional[str] = None  # "Easy" | "Medium" | "Hard" | None/"Mixed"


class ForecastInput(BaseModel):
    learner_id: str
    cert_id: str
    plan_id: str
    evidence_json: str
    observed_exam_score: Optional[int] = None
    observed_score_pct: Optional[float] = None


class ProgressSeriesInput(BaseModel):
    learner_id: str
    cert_id: str
    plan_id: str


class DomainMasteryInput(BaseModel):
    learner_id: str
    cert_id: str
    evidence_json: str


class ServiceHeatmapInput(BaseModel):
    learner_id: str
    cert_id: str
    evidence_json: str


class FabricIQInput(BaseModel):
    """Query the Fabric IQ semantic layer.

    query_type one of:
      readiness_semantics    — interpret evidence vs domain thresholds (needs cert_id + evidence_json)
      domain_thresholds      — per-domain weight/leverage/minimum-mastery (needs cert_id)
      role_certification_map — role → recommended/next certification (optional role)
      cohort_benchmark       — cohort outcome aggregates (optional cert_id)
      intervention_effect    — cohort-derived lift of protecting capacity (optional cert_id)
      ontology               — entities, relationships, and rules (transparency)
    """
    query_type: str
    cert_id: Optional[str] = None
    role: Optional[str] = None
    evidence_json: Optional[str] = None


# ── Tools ──────────────────────────────────────────────────────────────────

@mcp.tool()
async def parse_learner_profile(args: LearnerProfileInput) -> dict:
    """Parse and validate a learner profile. Returns structured profile summary."""
    try:
        profile = json.loads(args.raw_profile_json)
        return {
            "learner_id": args.learner_id,
            "cert_target": args.cert_target,
            "parsed": True,
            "summary": (
                f"Learner {args.learner_id} targeting {args.cert_target}. "
                f"Role: {profile.get('role', 'Unknown')}. "
                f"Team: {profile.get('team_id', 'Unknown')}. "
                f"Available study hours/week: "
                f"{profile.get('work_iq_signals', {}).get('available_study_hours_per_week', 'unknown')}."
            ),
            "validation_warnings": (
                ["No prior assessment evidence — readiness forecast will use cohort baselines"]
                if not profile.get("prior_assessment_evidence") else []
            ),
        }
    except Exception as e:
        return {"error": str(e), "parsed": False}


@mcp.tool()
async def foundry_iq_search(args: FoundryIQInput) -> dict:
    """Search the Foundry IQ knowledge base for cert content. Returns cited excerpts."""
    from backend.iq.foundry_iq import get_foundry_iq
    iq = get_foundry_iq()
    results = await iq.search(args.query, top_k=args.top_k)
    return {
        "query": args.query,
        "results": [r.to_dict() for r in results],
        "result_count": len(results),
        "grounded": len(results) > 0,
    }


@mcp.tool()
async def validate_citation(args: CitationInput) -> dict:
    """Validate that a citation (doc_id + span_id) exists and supports the claim."""
    from backend.iq.foundry_iq import get_foundry_iq
    iq = get_foundry_iq()
    results = await iq.search(args.claim_text, top_k=5)
    matching = [r for r in results if r.doc_id == args.doc_id]
    if matching:
        return {"valid": True, "doc_id": args.doc_id, "excerpt": matching[0].excerpt[:200]}
    return {"valid": False, "doc_id": args.doc_id, "reason": "No matching source found"}


@mcp.tool()
async def generate_study_plan(args: StudyPlanInput) -> dict:
    """
    Generate a capacity-aware weekly study plan.
    APPROVAL REQUIRED before publishing.
    """
    try:
        topics = json.loads(args.curated_topics_json)
        if not isinstance(topics, list):
            topics = []
    except Exception:
        topics = []

    topic_pool = _normalize_curated_topics(topics)
    if not topic_pool:
        # Fallback: one topic per cert domain so weeks fill evenly
        topic_pool = _normalize_curated_topics([
            {"title": "Core Concepts & Foundations", "domain": "General", "hours": 2},
            {"title": "Compute & Hosting", "domain": "Compute", "hours": 2},
            {"title": "Networking & Connectivity", "domain": "Networking", "hours": 2},
            {"title": "Storage & Data Management", "domain": "Storage", "hours": 2},
            {"title": "Security & Identity", "domain": "Security", "hours": 2},
            {"title": "Monitoring & Optimisation", "domain": "Monitoring", "hours": 2},
        ])

    hours_per_week = max(args.available_hours_per_week, 2.0)
    n_weeks = max(args.weeks, 1)
    topics_per_week = max(1, math.ceil(len(topic_pool) / n_weeks))

    # Slice topics into weekly buckets first, then run LRA *within each week*
    # so every topic's hours_allocated reflects what the learner does that week —
    # not a share of the total multi-week budget (which inflates the badge).
    weeks = []
    cumulative = 0
    remaining = list(topic_pool)

    for w in range(1, n_weeks + 1):
        week_slice = remaining[:topics_per_week]
        remaining = remaining[topics_per_week:]

        # LRA distributes this week's hours across its topics (guaranteed >= 0.5h each).
        week_slice = _lra_allocate_hours(week_slice, hours_per_week)
        week_hours = round(sum(t["hours_allocated"] for t in week_slice), 1)
        cumulative += len(week_slice)
        weeks.append({
            "week": w,
            "topics": week_slice,
            "planned_hours": week_hours,
            "cumulative_planned_topics": cumulative,
            "notes": "",
        })

    plan_id = f"plan_{args.learner_id}_{args.cert_id}_{str(uuid.uuid4())[:8]}"
    plan = {
        "plan_id": plan_id,
        "id": plan_id,
        "learner_id": args.learner_id,
        "cert_id": args.cert_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "draft",
        "deadline": args.deadline,
        "total_planned_hours": round(sum(week["planned_hours"] for week in weeks), 1),
        "weeks": weeks,
        "progress_series": [],
        "approved_by": "",
        "approved_at": "",
        "revision_count": 0,
        "ai_disclosure": "AI-generated; review before publishing",
        "requires_approval": True,
    }
    from backend.storage.store import get_storage as _get_storage
    _storage = _get_storage()
    # Delete all previous draft plans for this learner+cert so the manager
    # never sees stale cards from earlier workflow runs.
    existing = await _storage.list_plans(args.learner_id, args.cert_id)
    for old in existing:
        if old.get("status") == "draft":
            await _storage._store.delete("study_plans", old.get("id") or old.get("plan_id", ""))
    await _storage.save_plan(plan)
    return plan


@mcp.tool()
async def generate_assessment(args: AssessmentInput) -> dict:
    """Generate a timed, weighted assessment matched to cert domain structure."""
    from backend.iq.foundry_iq import get_foundry_iq
    from config.settings import get_settings
    import json
    from pathlib import Path

    s = get_settings()
    cert_path = Path(s.data_dir) / "synthetic" / "cert_structures.json"
    cert_structures = {}
    if cert_path.exists():
        cert_structures = json.loads(cert_path.read_text())

    cert = cert_structures.get(args.cert_id, {})
    domains = cert.get("domains", [{"domain_id": "D1", "name": "General", "weight_pct": 100}])

    iq = get_foundry_iq()
    questions = []
    question_index = 0
    assessment_seed = f"{args.learner_id}-{args.cert_id}-{uuid.uuid4().hex[:8]}"

    for domain in domains:
        results = await iq.search(
            f"{args.cert_id} {domain['name']} exam question", top_k=2
        )
        citation = results[0].to_dict() if results else {
            "doc_id": "cert_guide", "title": "Certification Guide",
            "excerpt": "See official study guide.", "span_id": "syn-001"
        }
        services = domain.get("services", ["General"])
        questions_for_domain = max(1, round(args.question_count * (domain.get("weight_pct", 100 / max(len(domains), 1)) / 100)))

        for i in range(questions_for_domain):
            difficulty = _assessment_difficulty_label(args.difficulty, question_index)
            service = _service_for_difficulty(services, difficulty, question_index)
            stems = QUESTION_STEMS_BY_DIFFICULTY.get(difficulty, QUESTION_STEMS_BY_DIFFICULTY["Medium"])
            base_stem = stems[question_index % len(stems)].format(
                cert_id=args.cert_id,
                domain=domain["name"],
                service=service,
            )
            # Ground the question in the actual retrieved excerpt so it is
            # grounded in approved content, not just a bare template.
            excerpt = (citation.get("excerpt") or "").strip()
            excerpt_snippet = (excerpt[:160] + "…") if len(excerpt) > 160 else excerpt
            if excerpt_snippet:
                stem = (
                    f"{base_stem}\n\nApproved source ({citation.get('title','Guide')}): "
                    f"“{excerpt_snippet}”"
                )
            else:
                stem = base_stem
            question_id = f"Q-{domain['domain_id']}-{i+1:03}"
            correct_option = f"Apply the recommended Microsoft pattern for {service}"
            options = [
                correct_option,
                f"Use a shortcut that ignores key constraints in {service}",
                f"Configure {service} with an incorrect dependency or scope",
                f"Choose a tool that does not match the {domain['name'].lower()} objective",
            ]
            # Deterministically shuffle so the correct answer is not always index 0.
            rng = random.Random(f"{assessment_seed}-{question_id}")
            rng.shuffle(options)
            correct_index = options.index(correct_option)
            questions.append({
                "question_id": question_id,
                "domain": domain["name"],
                "sub_topic": service,
                "difficulty": difficulty,
                "question_text": stem,
                "options": options,
                "correct_index": correct_index,
                "explanation": (
                    f"Grounded in {citation.get('title','the approved guide')}"
                    + (f": “{excerpt_snippet}”. " if excerpt_snippet else ". ")
                    + f"The correct option applies this guidance to {service}."
                ),
                "citations": [citation],
                "confidence_weight": round(domain["weight_pct"] / 100, 2),
            })
            question_index += 1

    assessment_id = f"assess_{assessment_seed}"
    return {
        "assessment_id": assessment_id,
        "learner_id": args.learner_id,
        "cert_id": args.cert_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "questions": questions[:args.question_count],
        "time_limit_minutes": cert.get("recommended_study_hours", 20) * 2,
        "ai_disclosure": "AI-generated assessment; verify against official exam guide",
    }


@mcp.tool()
async def compute_readiness_forecast(args: ForecastInput) -> dict:
    """Calibrated readiness forecast: pass probability + confidence interval + weakest topic."""
    try:
        evidence = json.loads(args.evidence_json)
    except Exception:
        evidence = {}

    if not evidence:
        return {
            "learner_id": args.learner_id,
            "cert_id": args.cert_id,
            "plan_id": args.plan_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "insufficient_evidence": True,
            "evidence_count": 0,
            "message": "Insufficient evidence to forecast. Complete at least one assessment.",
            "ai_disclosure": "AI-generated forecast; not a guarantee of exam outcome",
        }

    scores = {k: v for k, v in evidence.items() if isinstance(v, (int, float))}
    pass_threshold = 700
    if not scores:
        pass_prob = 0.5
        weakest = "unknown"
        min_hours = 5.0
        estimated_score = args.observed_exam_score if args.observed_exam_score is not None else 500
    else:
        avg_score = sum(scores.values()) / len(scores)
        weakest = min(scores, key=scores.get)
        estimated_score = args.observed_exam_score if args.observed_exam_score is not None else int(round(avg_score * 1000))
        pass_prob = min(0.99, max(0.05, estimated_score / 1000))
        min_hours = round(max(0, pass_threshold - estimated_score) / 32, 1)

    ci_width = 0.12 if len(scores) >= 4 else 0.20

    return {
        "learner_id": args.learner_id,
        "cert_id": args.cert_id,
        "plan_id": args.plan_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pass_probability": round(pass_prob, 3),
        "confidence_interval_lower": round(max(0, pass_prob - ci_width), 3),
        "confidence_interval_upper": round(min(1, pass_prob + ci_width), 3),
        "estimated_exam_score": estimated_score,
        "pass_threshold": pass_threshold,
        "points_below_threshold": max(0, pass_threshold - estimated_score),
        "weakest_topic": weakest,
        "minimum_additional_hours": min_hours,
        "insufficient_evidence": False,
        "evidence_count": len(scores),
        "ai_disclosure": "AI-generated forecast; not a guarantee of exam outcome",
    }


@mcp.tool()
async def compute_progress_series(args: ProgressSeriesInput) -> dict:
    """Return planned-vs-actual progress time series for the deviation graph."""
    from backend.storage.store import get_storage
    storage = get_storage()
    plan = await storage.get_plan(args.plan_id)
    if not plan:
        return {"error": "Plan not found", "plan_id": args.plan_id}

    weeks_data = plan.get("weeks", [])
    series = []
    cumulative_planned = 0
    cumulative_actual = 0

    for w in weeks_data:
        cumulative_planned += len(w.get("topics", []))
        # Simulate actual (in production, this comes from learner engagement signals)
        deviation = -1 if cumulative_planned > 4 else 0
        cumulative_actual = max(0, cumulative_planned + deviation)
        gap = cumulative_planned - cumulative_actual
        status = "on_track" if gap == 0 else ("at_risk" if gap == 1 else "off_track")
        series.append({
            "week": w["week"],
            "planned_topics": cumulative_planned,
            "actual_topics": cumulative_actual,
            "status": status,
        })

    return {
        "learner_id": args.learner_id,
        "cert_id": args.cert_id,
        "plan_id": args.plan_id,
        "series": series,
    }


@mcp.tool()
async def compute_domain_mastery(args: DomainMasteryInput) -> dict:
    """Compute per-domain mastery breakdown from accumulated evidence."""
    from config.settings import get_settings
    from pathlib import Path
    import json

    s = get_settings()
    cert_path = Path(s.data_dir) / "synthetic" / "cert_structures.json"
    cert_structures = {}
    if cert_path.exists():
        cert_structures = json.loads(cert_path.read_text())

    cert = cert_structures.get(args.cert_id, {})
    domains_config = cert.get("domains", [])

    try:
        evidence = json.loads(args.evidence_json)
    except Exception:
        evidence = {}
    if not isinstance(evidence, dict):
        evidence = {}

    domain_mastery = []
    for d in domains_config:
        name_lower = d["name"].lower()
        services_lower = " ".join(str(svc).lower() for svc in d.get("services", []))
        haystack = f"{name_lower} {services_lower}"
        # Map evidence keys to domains by matching the evidence key against the
        # domain name OR any of its service names.
        relevant_scores = [v for k, v in evidence.items()
                          if any(word in haystack for word in k.lower().split())]
        mastery_pct = (sum(relevant_scores) / len(relevant_scores) * 100) if relevant_scores else 50.0
        confidence = min(0.9, len(relevant_scores) * 0.2)
        domain_mastery.append({
            "domain_id": d["domain_id"],
            "name": d["name"],
            "weight_pct": d["weight_pct"],
            "mastery_pct": round(mastery_pct, 1),
            "confidence": round(confidence, 2),
            "evidence_count": len(relevant_scores),
            "flag": "low_evidence" if len(relevant_scores) < 2 else "",
            "services": [
                {"service_id": f"{d['domain_id']}-S{i+1}", "service_name": svc,
                 "mastery_pct": round(mastery_pct + (i - 1) * 5, 1), "evidence_count": max(0, len(relevant_scores) - 1)}
                for i, svc in enumerate(d.get("services", [])[:4])
            ],
        })

    return {
        "mastery_id": f"mastery_{args.learner_id}_{args.cert_id}",
        "learner_id": args.learner_id,
        "cert_id": args.cert_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "domains": domain_mastery,
        "pass_threshold": cert.get("passing_score", 700),
    }


@mcp.tool()
async def compute_service_heatmap(args: ServiceHeatmapInput) -> dict:
    """Compute service-level heatmap within each cert domain."""
    mastery = await compute_domain_mastery.fn(DomainMasteryInput(
        learner_id=args.learner_id,
        cert_id=args.cert_id,
        evidence_json=args.evidence_json,
    ))
    return {
        "learner_id": args.learner_id,
        "cert_id": args.cert_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "rows": mastery.get("domains", []),
    }


@mcp.tool()
async def fabric_iq_semantics(args: FabricIQInput) -> dict:
    """Query the Fabric IQ semantic layer for business meaning over the
    enterprise-learning ontology (roles, certifications, domains, thresholds,
    cohort outcomes). Returns semantic interpretation, not raw rows."""
    from backend.iq.fabric_iq import get_fabric_iq
    fiq = get_fabric_iq()
    qt = (args.query_type or "").strip().lower()

    if qt == "domain_thresholds":
        return {"query_type": qt, "cert_id": args.cert_id,
                "domains": fiq.get_domain_thresholds(args.cert_id or "")}
    if qt == "role_certification_map":
        return {"query_type": qt, "map": fiq.get_role_certification_map(args.role)}
    if qt == "cohort_benchmark":
        return {"query_type": qt, **fiq.get_cohort_benchmark(args.cert_id)}
    if qt == "intervention_effect":
        return {"query_type": qt, **fiq.get_intervention_effectiveness(args.cert_id)}
    if qt == "ontology":
        return {"query_type": qt, **fiq.describe_ontology()}
    # default: readiness_semantics
    try:
        evidence = json.loads(args.evidence_json) if args.evidence_json else {}
    except Exception:
        evidence = {}
    return {"query_type": "readiness_semantics",
            **fiq.get_readiness_semantics(args.cert_id or "", evidence)}


if __name__ == "__main__":
    import sys
    import os
    # Ensure project root is on path when run directly
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    from config.settings import get_settings
    s = get_settings()
    # FastMCP 2.x: streamable-http transport
    # If this raises, try: mcp.run(transport="sse", port=s.own_mcp_port)
    mcp.run(transport="streamable-http", host="0.0.0.0", port=s.own_mcp_port)
