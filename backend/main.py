"""
EnterpriseCertIQ — FastAPI backend
Provides REST + SSE endpoints for the React dashboard.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

import structlog
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.agents.factory import build_agents
from backend.core.telemetry import setup_telemetry
from backend.core.workflow import WorkflowOrchestrator
from backend.models.learner import LearnerProfile
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
    setup_telemetry()
    logger.info("EnterpriseCertIQ starting", backend=s.model_backend.value)
    yield
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


# ── Routes ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "backend": s.model_backend.value,
        "storage": s.storage_backend.value,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


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
    """Start the 6-agent pipeline for a learner. Returns run_id for SSE streaming."""
    learner = _load_learner(req.learner_id)
    if req.cert_target:
        learner.cert_target = req.cert_target

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
        retrospective_agent=agents["retrospective"],
        storage=storage,
    )

    async def _run():
        try:
            ctx = await orchestrator.run(
                learner,
                on_event=lambda evt: _broadcast(run_id, evt),
                run_id=run_id,
            )
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
            q.put_nowait({"type": "workflow_complete", "run_id": run_id,
                          "status": ctx.trace.final_status})
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


@app.get("/api/plans/{learner_id}")
async def get_plans(learner_id: str):
    return await storage.list_traces(learner_id)


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
    ))

    return {
        "assessment_id": req.assessment_id,
        "learner_id": req.learner_id,
        "score_pct": round(score_pct, 1),
        "questions_scored": total,
        "estimated_exam_score": estimated_score,
        "pass_threshold": pass_threshold,
        "passed": estimated_score >= pass_threshold,
        "forecast": forecast,
        "ai_disclosure": "AI-generated assessment result",
    }


@app.get("/api/mastery/{learner_id}/{cert_id}")
async def get_mastery(learner_id: str, cert_id: str):
    from backend.mcp_server.server import compute_domain_mastery, DomainMasteryInput
    import json
    from pathlib import Path

    path = Path(s.data_dir) / "synthetic" / "learners.json"
    learners = json.loads(path.read_text())
    learner = next((l for l in learners if l["learner_id"] == learner_id), None)
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
    evidence = learner.get("prior_assessment_evidence", {}) if learner else {}

    return await compute_readiness_forecast.fn(ForecastInput(
        learner_id=learner_id,
        cert_id=cert_id,
        plan_id="latest",
        evidence_json=json.dumps(evidence),
    ))


@app.get("/api/manager/{team_id}/insights")
async def manager_insights(team_id: str):
    """Return team-level manager insights using Work IQ signals."""
    from backend.iq.work_iq import get_work_iq
    all_learners = _load_all_learners()
    team_learners = [l for l in all_learners if l.team_id == team_id]
    if not team_learners:
        raise HTTPException(status_code=404, detail=f"Team {team_id} not found")
    wiq = get_work_iq()
    return await wiq.get_team_context(team_id, team_learners)


@app.get("/api/cert-structures/{cert_id}")
async def get_cert_structure(cert_id: str):
    import json
    from pathlib import Path
    path = Path(s.data_dir) / "synthetic" / "cert_structures.json"
    structures = json.loads(path.read_text())
    if cert_id not in structures:
        raise HTTPException(status_code=404, detail=f"Cert {cert_id} not found")
    return structures[cert_id]
