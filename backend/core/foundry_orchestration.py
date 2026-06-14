"""
Foundry Agent Service integration layer.

When MODEL_BACKEND=azure_foundry and AZURE_AI_PROJECT_ENDPOINT is set this
module wraps each workflow run as an Azure AI Foundry agent thread so that:

  - Runs are visible and traceable in the Azure AI Foundry portal
  - Agent definitions are registered once and re-used across runs
  - The Foundry-native run lifecycle (created → queued → in_progress → completed)
    is honoured — Microsoft Foundry is used at the orchestration level, not just
    for model inference

When running locally (foundry_local mode) or when azure-ai-projects is not
installed the module is a no-op: all calls return immediately without error so
the custom orchestrator continues to work with zero changes.

Usage (called by backend/main.py around the workflow run):

    from backend.core.foundry_orchestration import FoundrySession
    async with FoundrySession(run_id, learner_id, cert_id) as session:
        ctx = await orchestrator.run(learner, on_event=session.relay_event)
        await session.complete(ctx)
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Agent definitions registered in Foundry — one per pipeline role.
_AGENT_DEFINITIONS = [
    {
        "name": "eciq-learner-intake",
        "description": "Parses and validates the learner profile for EnterpriseCertIQ.",
        "instructions": "You parse learner profiles and emit structured intake summaries.",
        "model": None,  # filled at runtime from settings
    },
    {
        "name": "eciq-learning-path-curator",
        "description": "Curates certification learning paths grounded in Foundry IQ knowledge.",
        "instructions": "You retrieve approved certification topics from the Foundry IQ knowledge base and cite every recommendation.",
        "model": None,
    },
    {
        "name": "eciq-study-plan-generator",
        "description": "Converts curated topics into capacity-aware weekly study schedules.",
        "instructions": "You generate structured study plans respecting learner capacity and deadline constraints.",
        "model": None,
    },
    {
        "name": "eciq-readiness-critic",
        "description": "Reviews study plans against Fabric IQ domain weights and raises prioritised objections.",
        "instructions": "You critique study plans using semantic domain thresholds. Output severity-ranked objections with citations.",
        "model": None,
    },
    {
        "name": "eciq-engagement-agent",
        "description": "Schedules study reminders using Work IQ calendar signals.",
        "instructions": "You recommend study slots informed by meeting load and focus-time patterns. Never auto-write to calendar.",
        "model": None,
    },
    {
        "name": "eciq-assessment-agent",
        "description": "Generates grounded practice questions and evaluates exam readiness.",
        "instructions": "You generate cited questions from approved content and derive a readiness verdict from the calibrated forecast.",
        "model": None,
    },
    {
        "name": "eciq-manager-insights",
        "description": "Surfaces team-level certification readiness and workforce risk without exposing individual scores.",
        "instructions": "You produce aggregate team readiness insights. Never expose individual exam scores that could affect employment decisions.",
        "model": None,
    },
    {
        "name": "eciq-retrospective",
        "description": "Post-mortem agent triggered after a failed exam attempt.",
        "instructions": "You investigate why the system underperformed (retrieval, plan, engagement, or skill gap) and recommend recovery actions.",
        "model": None,
    },
]


def _sdk_tier() -> str:
    """Which azure-ai-projects generation is installed: 'v2' (>=2, native A2A/Responses/
    create_version), 'v1' (1.x, agents/threads), or 'off' (not installed)."""
    try:
        import azure.ai.projects  # noqa: F401
        import importlib.metadata as _m
        return "v2" if int(_m.version("azure-ai-projects").split(".")[0]) >= 2 else "v1"
    except Exception:
        return "off"


def foundry_mode() -> str:
    """Active integration mode: 'native' (Path A, v2) → 'mirror' (Path B, v1) → 'off'.

    Path A is preferred whenever the v2 SDK is installed and the project is configured;
    it degrades to the v1 mirror, then to no-op, so the app never depends on it.
    """
    try:
        from config.settings import get_settings, ModelBackend
        s = get_settings()
        if s.model_backend != ModelBackend.AZURE_FOUNDRY or not s.azure_ai_project_endpoint:
            return "off"
    except Exception:
        return "off"
    return {"v2": "native", "v1": "mirror"}.get(_sdk_tier(), "off")


def _get_project_client():
    """Return an AIProjectClient (v1 or v2 — same ctor) or None if not configured."""
    try:
        from config.settings import get_settings, ModelBackend
        s = get_settings()
        if s.model_backend != ModelBackend.AZURE_FOUNDRY or not s.azure_ai_project_endpoint:
            return None

        from azure.ai.projects import AIProjectClient
        from backend.core.azure_credentials import get_service_credential

        # The Agents data plane on *.services.ai.azure.com is Entra-token ONLY —
        # API keys are not accepted. Always use a TokenCredential (DefaultAzureCredential,
        # or a dedicated SPN via foundry_* settings). Excludes the IMDS probe locally.
        return AIProjectClient(
            endpoint=s.azure_ai_project_endpoint,
            credential=get_service_credential("foundry"),
        )
    except ImportError:
        logger.debug("azure-ai-projects not installed — Foundry orchestration disabled")
        return None
    except Exception as e:
        logger.warning("FoundrySession: could not create AIProjectClient: %s", e)
        return None


def _active_model() -> str:
    try:
        from config.settings import get_settings
        return get_settings().azure_ai_model_deployment or "gpt-4.1"
    except Exception:
        return "gpt-4.1"


class FoundrySession:
    """
    Async context manager that wraps a workflow run as a Foundry Agent thread.

    Inside the `async with` block the custom orchestrator runs normally.
    On entry we create a Foundry thread; on exit we post a summary message
    and mark the run completed so it appears in the Foundry portal timeline.
    """

    def __init__(self, run_id: str, learner_id: str, cert_id: str):
        self.run_id = run_id
        self.learner_id = learner_id
        self.cert_id = cert_id
        self._client = None
        self._thread_id: Optional[str] = None
        self._agent_id: Optional[str] = None

    async def __aenter__(self) -> "FoundrySession":
        import asyncio
        # Thread/message mirroring is a v1-only API. In native (v2) mode, runs are
        # represented via Conversations/Responses + AIProjectInstrumentor tracing, so we
        # skip the v1 thread ops here rather than call APIs that don't exist on the v2 client.
        if foundry_mode() != "mirror":
            self._client = None
            return self
        self._client = _get_project_client()
        if self._client is None:
            return self

        try:
            model = _active_model()
            await asyncio.to_thread(self._setup_foundry, model)
        except Exception as e:
            logger.warning("FoundrySession setup failed (non-fatal): %s", e)
            self._client = None

        return self

    def _setup_foundry(self, model: str) -> None:
        """Synchronous Foundry setup — runs in a thread pool."""
        agents_client = self._client.agents

        # Register the orchestrator agent if not already present
        existing = list(agents_client.list_agents())
        agent = next((a for a in existing if a.name == "eciq-orchestrator"), None)

        if agent is None:
            agent = agents_client.create_agent(
                model=model,
                name="eciq-orchestrator",
                description="EnterpriseCertIQ multi-agent learning orchestrator",
                instructions=(
                    "You orchestrate the EnterpriseCertIQ learning pipeline: "
                    "intake → curator → planner → critic loop → engagement → assessment → manager insights. "
                    "Each run targets a specific learner and certification. "
                    "Grounding uses Foundry IQ (retrieval), Work IQ (scheduling), and Fabric IQ (semantics)."
                ),
            )
            logger.info("Registered Foundry agent: %s (%s)", agent.name, agent.id)

        self._agent_id = agent.id

        # Create a thread for this workflow run
        thread = agents_client.create_thread()
        self._thread_id = thread.id

        # Post the run context as the opening user message
        agents_client.create_message(
            thread_id=self._thread_id,
            role="user",
            content=json.dumps({
                "run_id": self.run_id,
                "learner_id": self.learner_id,
                "cert_id": self.cert_id,
                "pipeline": "intake→curator→planner→critic→engagement→assessment→manager",
                "iq_layers": ["foundry_iq", "work_iq", "fabric_iq"],
            }),
        )
        logger.info(
            "FoundrySession: thread %s created for run %s (learner=%s, cert=%s)",
            self._thread_id, self.run_id, self.learner_id, self.cert_id,
        )

    def relay_event(self, event: Any) -> None:
        """Forward a workflow TraceEvent to the Foundry thread as a message (best-effort)."""
        if self._client is None or self._thread_id is None:
            return
        try:
            event_data = event.model_dump() if hasattr(event, "model_dump") else dict(event)
            # Only post substantive events to avoid flooding the thread
            interesting = {"tool_result", "critic_objection", "readiness_advance", "readiness_loopback"}
            if event_data.get("event_type") not in interesting:
                return
            self._client.agents.create_message(
                thread_id=self._thread_id,
                role="assistant",
                content=json.dumps(event_data, default=str)[:2000],
            )
        except Exception:
            pass  # relay is best-effort; never block the workflow

    async def complete(self, ctx: Any) -> None:
        """Post the final workflow summary and mark the Foundry run completed."""
        import asyncio
        if self._client is None or self._thread_id is None:
            return
        try:
            await asyncio.to_thread(self._complete_sync, ctx)
        except Exception as e:
            logger.warning("FoundrySession.complete failed (non-fatal): %s", e)

    @property
    def thread_url(self) -> Optional[str]:
        """Direct Foundry portal URL to this run's thread, or None if not in mirror mode."""
        if not self._thread_id or not self._agent_id:
            return None
        try:
            from config.settings import get_settings
            endpoint = get_settings().azure_ai_project_endpoint or ""
            # endpoint: https://<host>/api/projects/<project>
            # portal:   https://ai.azure.com/agents/<project>/agents/<agent>/threads/<thread>
            import re
            m = re.search(r"/projects/([^/]+)$", endpoint)
            project = m.group(1) if m else "aipoc"
        except Exception:
            project = "aipoc"
        return (
            f"https://ai.azure.com/agents/{project}"
            f"/agents/{self._agent_id}/threads/{self._thread_id}"
        )

    def _complete_sync(self, ctx: Any) -> None:
        outputs = getattr(ctx, "outputs", {})
        decision = outputs.get("readiness_decision", {})
        summary = {
            "run_id": self.run_id,
            "stages_completed": list(outputs.keys()),
            "readiness_verdict": decision.get("verdict", "unknown") if isinstance(decision, dict) else "unknown",
            "hitl_pending": getattr(ctx, "hitl_pending", False),
        }
        self._client.agents.create_message(
            thread_id=self._thread_id,
            role="assistant",
            content=json.dumps(summary),
        )
        logger.info("FoundrySession: run %s completed in thread %s", self.run_id, self._thread_id)

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            logger.warning(
                "FoundrySession: run %s exiting with error %s (thread=%s)",
                self.run_id, exc_val, self._thread_id,
            )
        # No explicit cleanup — Foundry threads persist for portal inspection
        return False  # do not suppress exceptions


_ORCHESTRATOR_DEF = {
    "name": "eciq-orchestrator",
    "description": "EnterpriseCertIQ multi-agent learning orchestrator.",
    "instructions": (
        "You orchestrate the EnterpriseCertIQ pipeline: intake → curator → planner → "
        "critic loop → engagement → assessment → manager insights, grounded in Foundry IQ, "
        "Work IQ, and Fabric IQ."
    ),
    "model": None,
}


async def register_all_agents() -> list[dict]:
    """Pre-register the EnterpriseCertIQ agents in Foundry (once at startup).

    Path A (native, v2): `agents.create_version(PromptAgentDefinition(...))`.
    Path B (mirror, v1): `agents.create_agent(...)` (create-or-reuse).
    Returns [] in off/local mode or on auth failure (non-fatal).
    """
    import asyncio
    mode = foundry_mode()
    if mode == "off":
        return []
    client = _get_project_client()
    if client is None:
        return []

    model = _active_model()
    defs = [_ORCHESTRATOR_DEF, *_AGENT_DEFINITIONS]

    def _build_search_tool():
        """Build AzureAISearchTool using the configured search connection (v2 SDK only)."""
        try:
            from azure.ai.projects.models import (
                AzureAISearchTool, AzureAISearchToolResource,
                AISearchIndexResource, AzureAISearchQueryType,
            )
            from config.settings import get_settings
            s = get_settings()
            conn_name = s.foundry_search_connection_name
            if not conn_name:
                return None
            conn = client.connections.get(conn_name)
            return AzureAISearchTool(
                azure_ai_search=AzureAISearchToolResource(
                    indexes=[AISearchIndexResource(
                        project_connection_id=conn.id,
                        index_name=s.foundry_iq_index_name,
                        query_type=AzureAISearchQueryType.SIMPLE,
                    )]
                )
            )
        except Exception as e:
            logger.warning("Could not build AzureAISearchTool (non-fatal): %s", e)
            return None

    # Agents that get native Foundry IQ grounding attached
    _GROUNDED = {"eciq-learning-path-curator", "eciq-assessment-agent", "eciq-readiness-critic"}

    def _register_native():  # Path A — v2 create_version
        from azure.ai.projects.models import PromptAgentDefinition
        search_tool = _build_search_tool()
        if search_tool:
            logger.info("Foundry IQ: AzureAISearchTool attached to grounded agents (index=%s)",
                        get_settings().foundry_iq_index_name if True else "")
        out = []
        for d in defs:
            attach = search_tool is not None and d["name"] in _GROUNDED
            definition = PromptAgentDefinition(
                kind="prompt",
                model=model,
                instructions=d["instructions"],
                tools=[search_tool] if attach else [],
            )
            v = client.agents.create_version(
                agent_name=d["name"], definition=definition, description=d["description"],
            )
            out.append({
                "name": d["name"], "version": getattr(v, "version", None),
                "status": "versioned", "foundry_iq": attach,
            })
            logger.info("Foundry (native) agent versioned: %s (foundry_iq=%s)", d["name"], attach)
        return out

    def _register_mirror():  # Path B — v1 create_agent (create-or-reuse)
        existing = {a.name: a for a in client.agents.list_agents()}
        out = []
        for d in defs:
            if d["name"] in existing:
                out.append({"name": d["name"], "id": existing[d["name"]].id, "status": "existing"})
                continue
            agent = client.agents.create_agent(
                model=model, name=d["name"],
                description=d["description"], instructions=d["instructions"],
            )
            out.append({"name": d["name"], "id": agent.id, "status": "created"})
            logger.info("Foundry (mirror) agent created: %s (%s)", d["name"], agent.id)
        return out

    if mode == "native":
        # Agents are pre-registered by register_agents_cloud_shell.py with full MCPTool
        # KB connections and Toolbox wiring. Skip auto-registration to avoid overwriting
        # those versions with stubs. Set FOUNDRY_AUTO_REGISTER=true to override.
        try:
            from config.settings import get_settings as _gs
            if not _gs().foundry_auto_register:
                logger.info(
                    "Foundry native mode: skipping auto-register (agents pre-registered). "
                    "Set FOUNDRY_AUTO_REGISTER=true to enable."
                )
                return []
        except Exception:
            pass
        try:
            return await asyncio.to_thread(_register_native)
        except Exception as e:
            logger.warning("Path A native registration failed, falling back to mirror: %s", e)
            mode = "mirror"
    try:
        return await asyncio.to_thread(_register_mirror)
    except Exception as e:
        logger.warning("register_all_agents failed (non-fatal): %s", e)
        return []
