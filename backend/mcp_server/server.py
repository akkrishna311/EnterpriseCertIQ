"""
EnterpriseCertIQ own MCP server (FastMCP).
Exposes 9 typed tools consumed by the 6 agents.

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


QUESTION_STEMS = [
    "[Synthetic] For {cert_id} in {domain}, which implementation best fits {service}?",
    "[Synthetic] A developer is working on {service} within {domain} for {cert_id}. What should they choose?",
    "[Synthetic] Which approach aligns with Microsoft guidance for {service} under {domain} in {cert_id}?",
    "[Synthetic] When designing {service} for the {domain} objective in {cert_id}, what is the recommended action?",
]


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


class ForecastInput(BaseModel):
    learner_id: str
    cert_id: str
    plan_id: str
    evidence_json: str


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
    except Exception:
        topics = [{"title": "Foundations", "domain": "General", "hours": 3}]

    topic_pool = _normalize_curated_topics(topics)
    if not topic_pool:
        topic_pool = _normalize_curated_topics([
            {"title": "Foundations", "domain": "General", "hours": 3}
        ])

    hours_per_week = max(args.available_hours_per_week, 2.0)
    weeks = []
    cumulative = 0
    topics_per_week = max(1, math.ceil(len(topic_pool) / max(args.weeks, 1)))

    for w in range(1, args.weeks + 1):
        week_topics = topic_pool[:topics_per_week]
        week_hours = min(hours_per_week, sum(t.get("hours_allocated", 2) for t in week_topics))
        cumulative += len(week_topics)
        weeks.append({
            "week": w,
            "topics": week_topics,
            "planned_hours": round(week_hours, 1),
            "cumulative_planned_topics": cumulative,
            "notes": "",
        })
        topic_pool = topic_pool[len(week_topics):]

    plan_id = f"plan_{args.learner_id}_{args.cert_id}_{str(uuid.uuid4())[:8]}"
    return {
        "plan_id": plan_id,
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
            service = services[i % max(len(services), 1)]
            difficulty = ["Easy", "Medium", "Hard"][question_index % 3]
            stem = QUESTION_STEMS[question_index % len(QUESTION_STEMS)].format(
                cert_id=args.cert_id,
                domain=domain["name"],
                service=service,
            )
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
                    f"The correct option applies Microsoft guidance for {service}. "
                    f"Source: {citation['title']}."
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
    if not scores:
        pass_prob = 0.5
        weakest = "unknown"
        min_hours = 5.0
    else:
        avg_score = sum(scores.values()) / len(scores)
        pass_prob = min(0.95, max(0.05, (avg_score - 0.3) / 0.5))
        weakest = min(scores, key=scores.get)
        min_hours = max(0.0, round((0.75 - avg_score) * 30, 1))

    ci_width = 0.12 if len(scores) >= 4 else 0.20
    estimated_score = int(pass_prob * 1000)
    pass_threshold = 700

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
