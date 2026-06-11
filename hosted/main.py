"""EnterpriseCertIQ — Hosted Agent entrypoint for Foundry Agent Service.

Wraps the full multi-agent pipeline (WorkflowOrchestrator) behind the Foundry Hosted-Agent
runtime contract: a Responses-style endpoint + a /readiness health path, served on port 8088.

It prefers the official protocol library (`azure-ai-agentserver-responses`, the
`@app.response_handler` decorator) when present in the image; otherwise it falls back to a
minimal FastAPI server implementing the same contract, so the container is runnable and
testable locally without the preview SDK. Build with Dockerfile.hosted; deploy via
`create_version(HostedAgentDefinition(...))` — see docs/foundry-hosted-agents.md.
"""
from __future__ import annotations

import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hosted-agent")

_DEFAULT_LEARNER = "L-1004"
_LEARNER_RE = re.compile(r"\bL-\d{3,5}\b")


async def run_pipeline(input_text: str) -> str:
    """Run the multi-agent pipeline for the learner referenced in the prompt and return a
    concise, manager-ready readiness summary as text."""
    from backend.main import _load_learner, storage          # reuse the app's wiring
    from backend.agents.factory import build_agents
    from backend.core.workflow import WorkflowOrchestrator

    m = _LEARNER_RE.search(input_text or "")
    learner_id = m.group(0) if m else _DEFAULT_LEARNER
    learner = _load_learner(learner_id)

    agents = build_agents(on_event=lambda _evt: None)
    orch = WorkflowOrchestrator(
        intake_agent=agents["intake"], curator_agent=agents["curator"],
        planner_agent=agents["planner"], critic_agent=agents["critic"],
        engagement_agent=agents["engagement"], manager_agent=agents["manager"],
        assessment_agent=agents["assessment"], retrospective_agent=agents["retrospective"],
        storage=storage,
    )
    ctx = await orch.run(learner)
    out = getattr(ctx, "outputs", {}) or {}
    decision = out.get("readiness_decision", {}) if isinstance(out.get("readiness_decision"), dict) else {}
    verdict = decision.get("verdict", "unknown")
    weakest = decision.get("weakest_topic") or decision.get("weakest_area") or "—"
    stages = ", ".join(out.keys())
    return (
        f"EnterpriseCertIQ readiness for {learner_id} ({learner.cert_target}): "
        f"verdict={verdict}; weakest area={weakest}. "
        f"Pipeline stages completed: {stages}. (Grounded via Foundry IQ; "
        f"semantics via Fabric IQ; schedule via Work IQ signals. Synthetic data.)"
    )


# ── Runtime contract ────────────────────────────────────────────────────────
try:
    # Official Foundry protocol library (preview). Serves /readiness on 8088 automatically.
    from azure.ai.agentserver.responses import app, TextResponse  # type: ignore

    @app.response_handler  # type: ignore
    async def handler(request, context, cancellation_signal):    # noqa: ANN001
        user_text = getattr(request, "input", None) or getattr(request, "text", "") or str(request)
        return TextResponse(await run_pipeline(user_text))

    logger.info("Hosted Agent: using azure-ai-agentserver-responses protocol")

except Exception:  # pragma: no cover - exercised only when the lib is absent
    # Fallback: minimal FastAPI implementing the same contract (testable without the SDK).
    from fastapi import FastAPI
    from pydantic import BaseModel

    app = FastAPI(title="EnterpriseCertIQ Hosted Agent (fallback)")

    class _Req(BaseModel):
        input: str = ""

    @app.get("/readiness")
    async def readiness():
        return {"status": "ready"}

    @app.post("/responses")
    async def responses(body: _Req):
        return {"output_text": await run_pipeline(body.input)}

    logger.info("Hosted Agent: azure-ai-agentserver-responses not installed — FastAPI fallback")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8088)
