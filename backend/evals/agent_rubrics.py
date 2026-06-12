"""
Rubric-based agent evaluation harness.

Deterministic, zero-credential quality rubrics for each agent's *structured output*
E1–E7 checks with a pass threshold, adapted to EnterpriseCertIQ's Pydantic contracts.

Unlike `groundedness.py` (LLM-as-judge, Azure), these rubrics are pure-Python
assertions over the output shape and content rules, so they run in CI with no model
and no network — every check is reproducible.

Usage:
    from backend.evals.agent_rubrics import evaluate_agent_output, batch_evaluate
    result = evaluate_agent_output("plan_generator", plan_dict)
    assert result.passed
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

PASS_THRESHOLD = 0.8


@dataclass
class RubricResult:
    agent: str
    checks: list[dict] = field(default_factory=list)
    score: float = 0.0
    passed: bool = False

    def add(self, check_id: str, description: str, passed: bool) -> None:
        self.checks.append({"id": check_id, "description": description, "passed": bool(passed)})

    def finalize(self, threshold: float = PASS_THRESHOLD) -> "RubricResult":
        total = len(self.checks)
        ok = sum(1 for c in self.checks if c["passed"])
        self.score = round(ok / total, 3) if total else 0.0
        self.passed = self.score >= threshold
        return self


def _as_dict(payload: Any) -> dict:
    if hasattr(payload, "model_dump"):
        return payload.model_dump(mode="json")
    return payload if isinstance(payload, dict) else {}


def _as_list(payload: Any) -> list:
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    return payload if isinstance(payload, list) else payload.get("root", []) if isinstance(payload, dict) else []


# ── Per-agent rubrics ────────────────────────────────────────────────────────

def _rubric_curator(payload: Any) -> RubricResult:
    r = RubricResult("curator")
    topics = _as_list(payload)
    r.add("C1", "Returns at least one topic", len(topics) >= 1)
    r.add("C2", "Every topic has a citation or MS Learn URL",
          all((t.get("citations") or t.get("ms_learn_url")) for t in topics) if topics else False)
    r.add("C3", "All topic hours within [0.5, 12]",
          all(0.5 <= float(t.get("hours", 0)) <= 12 for t in topics) if topics else False)
    titles = [t.get("title", "").casefold() for t in topics]
    r.add("C4", "No duplicate topic titles", len(titles) == len(set(titles)))
    return r.finalize()


def _rubric_plan(payload: Any) -> RubricResult:
    r = RubricResult("plan_generator")
    d = _as_dict(payload)
    required = {"plan_id", "learner_id", "cert_id", "weeks", "total_planned_hours"}
    r.add("P1", "Valid StudyPlan schema keys", required.issubset(d.keys()))
    weeks = d.get("weeks", [])
    r.add("P2", "At least one week", len(weeks) >= 1)
    r.add("P3", "Total planned hours > 0", float(d.get("total_planned_hours", 0)) > 0)
    r.add("P4", "Every week carries topics", all(w.get("topics") for w in weeks) if weeks else False)
    r.add("P5", "Plan starts as draft (HITL)", d.get("status", "draft") == "draft")
    return r.finalize()


def _rubric_critic(payload: Any) -> RubricResult:
    r = RubricResult("readiness_critic")
    d = _as_dict(payload)
    objs = d.get("objections", [])
    r.add("CR1", "Objections (if any) are well-formed",
          all({"severity", "description", "recommendation"} <= set(o) for o in objs) if objs else True)
    r.add("CR2", "Severities valid",
          all(o.get("severity") in {"red", "amber"} for o in objs) if objs else True)
    r.add("CR3", "Forecast attached", isinstance(d.get("forecast"), dict))
    r.add("CR4", "overall_risk valid", d.get("overall_risk") in {"high", "medium", "low"})
    return r.finalize()


def _rubric_assessment(payload: Any) -> RubricResult:
    r = RubricResult("assessment")
    d = _as_dict(payload)
    r.add("A1", "Verdict valid",
          d.get("readiness_verdict") in {"ready", "not_ready", "insufficient_evidence"})
    r.add("A2", "Recommendation valid",
          d.get("recommendation") in {"advance", "remediate", "gather_evidence"})
    r.add("A3", "Pass probability in [0,1]", 0.0 <= float(d.get("pass_probability", 0)) <= 1.0)
    sq = d.get("sample_questions", [])
    r.add("A4", "Sample questions cited (if present)",
          all(q.get("citation") for q in sq) if sq else True)
    r.add("A5", "Booking verdict present (GO / CONDITIONAL_GO / NOT_YET)",
          d.get("booking_verdict") in {"GO", "CONDITIONAL_GO", "NOT_YET"})
    return r.finalize()


def _rubric_engagement(payload: Any) -> RubricResult:
    r = RubricResult("engagement")
    d = _as_dict(payload)
    r.add("E1", "Recommended study slots present", len(d.get("recommended_study_slots", [])) >= 1)
    r.add("E2", "Capacity risk valid", d.get("capacity_risk") in {"low", "medium", "high"})
    r.add("E3", "Does not auto-write calendar (disclosure)", "calendar" in d.get("ai_disclosure", "").lower())
    return r.finalize()


def _rubric_manager(payload: Any) -> RubricResult:
    r = RubricResult("manager_insights")
    d = _as_dict(payload)
    dist = d.get("readiness_distribution", {})
    r.add("M1", "Readiness distribution present", {"on_track", "at_risk"} <= set(dist))
    r.add("M2", "Has manager actions", len(d.get("manager_actions", [])) >= 1)
    # Privacy: no per-learner raw exam score leaked in the aggregate text fields.
    blob = " ".join(str(v) for v in d.values() if isinstance(v, str))
    r.add("M3", "No individual exam score leaked in summary text",
          "estimated_exam_score" not in blob)
    r.add("M4", "Peer pairs (if any) name both sides",
          all(p.get("learner_a") and p.get("learner_b") for p in d.get("peer_learning_pairs", [])))
    return r.finalize()


def _rubric_retrospective(payload: Any) -> RubricResult:
    r = RubricResult("retrospective")
    d = _as_dict(payload)
    valid_causes = {"engagement_gap", "retrieval_quality", "plan_quality", "skill_gap", "mixed"}
    r.add("R1", "root_cause is one of the valid taxonomy values",
          d.get("root_cause") in valid_causes)
    r.add("R2", "Evidence list is non-empty",
          len(d.get("evidence", [])) >= 1)
    r.add("R3", "Recovery recommendations present",
          len(d.get("recovery_recommendations", [])) >= 1)
    r.add("R4", "next_plan_adjustments present with extra_hours_on_weak_areas",
          isinstance(d.get("next_plan_adjustments", {}).get("extra_hours_on_weak_areas"), dict))
    return r.finalize()


_RUBRICS: dict[str, Callable[[Any], RubricResult]] = {
    "curator": _rubric_curator,
    "plan_generator": _rubric_plan,
    "readiness_critic": _rubric_critic,
    "assessment": _rubric_assessment,
    "engagement": _rubric_engagement,
    "manager_insights": _rubric_manager,
    "retrospective": _rubric_retrospective,
}


def evaluate_agent_output(agent_name: str, payload: Any,
                          threshold: float = PASS_THRESHOLD) -> RubricResult:
    rubric = _RUBRICS.get(agent_name)
    if rubric is None:
        return RubricResult(agent_name, checks=[{"id": "NA", "description": "no rubric", "passed": True}],
                            score=1.0, passed=True)
    result = rubric(payload)
    result.finalize(threshold)
    return result


def batch_evaluate(samples: dict[str, Any], threshold: float = PASS_THRESHOLD) -> dict:
    """Evaluate {agent_name: payload} and return a summary with per-agent scores."""
    results = {name: evaluate_agent_output(name, payload, threshold)
               for name, payload in samples.items()}
    scores = [r.score for r in results.values()]
    return {
        "results": {n: {"score": r.score, "passed": r.passed, "checks": r.checks}
                    for n, r in results.items()},
        "mean_score": round(sum(scores) / len(scores), 3) if scores else 0.0,
        "all_passed": all(r.passed for r in results.values()),
        "threshold": threshold,
    }
