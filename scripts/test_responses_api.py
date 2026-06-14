"""
Smoke-test for the 3 Foundry-grounded agents (Responses API path).

Tests curator, critic, and assessment with the same message shapes
the workflow.py sends so the JSON parsing + Pydantic validation is
exercised end-to-end under realistic conditions.

Run from repo root:
    python scripts/test_responses_api.py
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ.setdefault("FOUNDRY_USE_RESPONSES_API", "true")

# ── Minimal synthetic context (mirrors what workflow.py provides) ──────────
_LEARNER = {
    "learner_id": "L-smoke-001",
    "cert_target": "AZ-204",
    "role": "Software Engineer",
    "team_id": "T-ENGG",
    "deadline": "2026-09-01",
    "work_iq_signals": {
        "available_study_hours_per_week": 5,
        "focus_hours_per_week": 20,
        "meeting_hours_per_week": 10,
        "preferred_learning_slot": "morning",
        "upcoming_milestones": [],
        "source": "synthetic",
    },
    "prior_assessment_evidence": None,
    "prior_attempts": [],
    "has_prior_failures": False,
}

_DOMAIN_THRESHOLDS = {
    "Azure App Service & Functions": 0.22,
    "Azure Storage": 0.15,
    "Azure Cosmos DB": 0.15,
    "Azure Security & Identity": 0.20,
    "Azure Monitoring & Diagnostics": 0.13,
    "API Management & Integration": 0.15,
}

_SAMPLE_PLAN = {
    "plan_id": "smoke-plan-001",
    "learner_id": "L-smoke-001",
    "cert_id": "AZ-204",
    "weeks": [
        {
            "week": 1,
            "topics": [
                {"title": "Azure App Service deployment", "domain": "Azure App Service & Functions",
                 "hours_allocated": 3.0},
                {"title": "Azure Functions triggers & bindings", "domain": "Azure App Service & Functions",
                 "hours_allocated": 2.0},
            ],
        },
        {
            "week": 2,
            "topics": [
                {"title": "Blob & Queue Storage", "domain": "Azure Storage",
                 "hours_allocated": 2.5},
                {"title": "Azure Cosmos DB partitioning", "domain": "Azure Cosmos DB",
                 "hours_allocated": 2.5},
            ],
        },
    ],
}

_SAMPLE_FORECAST = {
    "pass_probability": 0.52,
    "estimated_exam_score": 640,
    "pass_threshold": 700,
    "weakest_topic": "Azure Security & Identity",
    "insufficient_evidence": False,
}

# ── Agent messages (same shape as workflow.py) ─────────────────────────────

def _curator_messages():
    return [{
        "role": "user",
        "content": (
            "Learner profile:\nRole: Software Engineer targeting AZ-204. "
            "5 study hours/week available, deadline 2026-09-01.\n\n"
            "Cert target: AZ-204\n"
            "Map this cert to skill topics. Retrieve approved content and "
            "Microsoft Learn paths. Cite every recommendation."
        ),
    }]

def _critic_messages():
    return [{
        "role": "user",
        "content": (
            f"Learner: {json.dumps(_LEARNER)}\n\n"
            f"Fabric IQ weighted domain thresholds (highest leverage first):\n"
            f"{json.dumps(_DOMAIN_THRESHOLDS, indent=2)}\n\n"
            f"Study plan (round 1):\n{json.dumps(_SAMPLE_PLAN, indent=2)}\n\n"
            "Identify weaknesses: under-allocated high-leverage domains, schedule "
            "conflicts, prerequisite ordering. Weight objections by domain leverage. "
            "Return objections as JSON list with severity red/amber, description, "
            "recommendation, citation."
        ),
    }]

def _assessment_messages():
    return [{
        "role": "user",
        "content": (
            f"Learner: {json.dumps(_LEARNER)}\n\n"
            f"Calibrated readiness forecast:\n{json.dumps(_SAMPLE_FORECAST, indent=2)}\n\n"
            f"Study plan:\n{json.dumps(_SAMPLE_PLAN, indent=2)[:600]}\n\n"
            "Generate grounded, cited practice questions; evaluate readiness; "
            "and recommend advance / remediate / gather_evidence. Ground the "
            "next-step certification recommendation with foundry_iq_search. "
            "Return the AssessmentOutput JSON."
        ),
    }]

# ── Helpers ────────────────────────────────────────────────────────────────

def _check_curator(result) -> list[str]:
    issues = []
    parsed = result.parsed
    if parsed is None:
        issues.append("parsed=None — JSON schema hint did not produce parseable JSON")
        return issues
    try:
        topics = parsed.root if hasattr(parsed, "root") else parsed
        if not isinstance(topics, list) or len(topics) == 0:
            issues.append("CuratedTopicList is empty")
        else:
            print(f"    Topics ({len(topics)}):")
            for t in topics[:4]:
                td = t.model_dump() if hasattr(t, "model_dump") else dict(t)
                print(f"      - [{td.get('priority','?')}] {td.get('title','?')} "
                      f"| domain={td.get('domain','?')} | hours={td.get('hours','?')}")
            if len(topics) > 4:
                print(f"      ... +{len(topics)-4} more")
    except Exception as e:
        issues.append(f"Topic inspection error: {e}")
    return issues

def _check_critic(result) -> list[str]:
    issues = []
    parsed = result.parsed
    if parsed is None:
        issues.append("parsed=None — JSON schema hint did not produce parseable JSON")
        return issues
    pd = parsed.model_dump()
    objections = pd.get("objections", [])
    if not objections:
        issues.append("objections list is empty (critic produced no objections)")
    else:
        print(f"    Objections ({len(objections)}):")
        for o in objections[:3]:
            print(f"      - [{o.get('severity','?').upper()}] {o.get('description','')[:80]}")
        if len(objections) > 3:
            print(f"      ... +{len(objections)-3} more")
    has_red = any(o.get("severity") == "red" for o in objections)
    has_amber = any(o.get("severity") == "amber" for o in objections)
    print(f"    Severities: red={has_red}  amber={has_amber}")
    print(f"    overall_risk: {pd.get('overall_risk','?')}")
    return issues

def _check_assessment(result) -> list[str]:
    issues = []
    parsed = result.parsed
    if parsed is None:
        issues.append("parsed=None — JSON schema hint did not produce parseable JSON")
        return issues
    pd = parsed.model_dump()
    print(f"    readiness_verdict : {pd.get('readiness_verdict','?')}")
    print(f"    booking_verdict   : {pd.get('booking_verdict','?')}")
    print(f"    recommendation    : {pd.get('recommendation','?')}")
    print(f"    pass_probability  : {pd.get('pass_probability','?')}")
    print(f"    weak_areas        : {pd.get('weak_areas', [])}")
    qs = pd.get("sample_questions", [])
    if not qs:
        issues.append("sample_questions is empty (no practice questions generated)")
    else:
        print(f"    sample_questions  : {len(qs)}")
        for q in qs[:2]:
            print(f"      Q: {q.get('question_text','')[:80]}")
            print(f"         domain={q.get('domain','?')}  citation={q.get('citation','')[:50]}")
    return issues

# ── Main ───────────────────────────────────────────────────────────────────

async def test_agent(role: str, messages_fn, checker_fn, call_grounded_agent):
    label = role.upper()
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")

    result = await call_grounded_agent(role, messages_fn(), run_id=f"smoke-{role}")

    if result is None:
        print(f"  [FAIL] call_grounded_agent returned None — check logs above")
        return False

    status = "OK" if result.parsed is not None else "PROSE"
    print(f"  [{status}]  chars={len(result.content)}  "
          f"parsed={'YES ('+type(result.parsed).__name__+')' if result.parsed else 'NO'}")

    issues = checker_fn(result)

    if issues:
        for issue in issues:
            print(f"  [WARN] {issue}")
        print(f"\n  --- raw content (first 400 chars) ---")
        print(result.content[:400])
        return False

    return True


async def main():
    from backend.core.foundry_grounded_agent import responses_api_enabled, call_grounded_agent

    print("=== Foundry Responses API — All 3 grounded agents smoke-test ===\n")
    print(f"responses_api_enabled() -> {responses_api_enabled()}")

    if not responses_api_enabled():
        print("\n[SKIP] Not enabled.")
        print("  Requires: MODEL_BACKEND=azure_foundry  AZURE_AI_PROJECT_ENDPOINT=<set>")
        print("  in .env.local  AND  FOUNDRY_USE_RESPONSES_API=true")
        return

    results = {}

    results["curator"] = await test_agent(
        "curator", _curator_messages, _check_curator, call_grounded_agent
    )
    results["critic"] = await test_agent(
        "critic", _critic_messages, _check_critic, call_grounded_agent
    )
    results["assessment"] = await test_agent(
        "assessment", _assessment_messages, _check_assessment, call_grounded_agent
    )

    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    all_pass = True
    for role, passed in results.items():
        icon = "[PASS]" if passed else "[FAIL]"
        print(f"  {icon}  {role}")
        if not passed:
            all_pass = False

    if all_pass:
        print("\n  All 3 agents returned structured JSON. Foundry path is cloud-ready.")
    else:
        print("\n  One or more agents returned prose or None.")
        print("  Check the 'parsed=FAILED' log lines above — the workflow will")
        print("  fall back to BaseAgent (Azure OpenAI direct) for those agents.")
    print()

asyncio.run(main())
