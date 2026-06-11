"""
Responses API caller for the 3 Foundry-IQ-grounded agents.

When FOUNDRY_USE_RESPONSES_API=true (and MODEL_BACKEND=azure_foundry), the curator,
critic, and assessment agents are invoked via the Foundry Responses API with an
agent_reference, so the knowledge-base retrieval and citation injection happen
server-side inside Foundry Agent Service.

The function `call_grounded_agent` returns an AgentResult — the same type that
BaseAgent.run() returns — so callers in workflow.py can switch paths with a single
if-check and fall back to the existing BaseAgent path transparently.

This module is a no-op when:
  - FOUNDRY_USE_RESPONSES_API is false/unset
  - MODEL_BACKEND != azure_foundry
  - azure-ai-projects is not installed (ImportError caught silently)
  - the Responses API call itself fails (falls back gracefully)
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Foundry agent names for the 3 grounded agents (must match what's registered in portal)
GROUNDED_AGENT_NAMES = {
    "curator":    "eciq-learning-path-curator",
    "critic":     "eciq-readiness-critic",
    "assessment": "eciq-assessment-agent",
}


def responses_api_enabled() -> bool:
    """True when Responses API path is configured and active."""
    try:
        from config.settings import get_settings, ModelBackend
        s = get_settings()
        return (
            s.model_backend == ModelBackend.AZURE_FOUNDRY
            and s.foundry_use_responses_api
            and bool(s.azure_ai_project_endpoint)
        )
    except Exception:
        return False


def _get_credential():
    """Return a TokenCredential for AIProjectClient.

    Priority:
    1. Service Principal (AZURE_CLIENT_ID + AZURE_CLIENT_SECRET + AZURE_TENANT_ID) —
       recommended for backend services; DefaultAzureCredential picks these up automatically.
    2. API key shim — wraps AZURE_AI_API_KEY as a fake token so AIProjectClient accepts
       it for URL construction. Works for the project-level OpenAI surface; the agent-specific
       endpoint may require a real Entra identity (RBAC). If that call fails, the caller
       falls back to BaseAgent.
    """
    import time
    from azure.core.credentials import AccessToken
    from config.settings import get_settings
    import os
    s = get_settings()

    # DefaultAzureCredential automatically uses env vars AZURE_CLIENT_ID / SECRET / TENANT_ID
    # when set — this is the recommended path for backend services without az login.
    has_spn = all([
        os.environ.get("AZURE_CLIENT_ID") or s.azure_ai_api_key == "",  # proxy: SPN vars present
        os.environ.get("AZURE_CLIENT_SECRET"),
        os.environ.get("AZURE_TENANT_ID"),
    ])
    if has_spn or not s.azure_ai_api_key:
        from backend.core.azure_credentials import get_service_credential
        return get_service_credential("foundry")

    # API key shim — satisfies TokenCredential interface for URL construction.
    # The key is forwarded as an api-key header by the underlying HTTP layer.
    class _ApiKeyCredential:
        def __init__(self, key: str):
            self._key = key

        def get_token(self, *scopes, **kwargs) -> AccessToken:
            return AccessToken(self._key, int(time.time()) + 3600)

    return _ApiKeyCredential(s.azure_ai_api_key)


def _get_openai_client(agent_name: str | None = None):
    """Return a synchronous OpenAI client via AIProjectClient.get_openai_client().

    When agent_name is provided, the client is pre-bound to the agent-specific endpoint:
      {project_endpoint}/agents/{agent_name}/endpoint/protocols/openai/v1/responses
    This ensures the Responses API call routes through the registered agent's
    instructions, knowledge base, and tools — required for hackathon "hosted agent" criteria.

    Falls back to the general project OpenAI surface when agent_name is None.
    """
    from azure.ai.projects import AIProjectClient
    from config.settings import get_settings
    s = get_settings()

    client = AIProjectClient(
        endpoint=s.azure_ai_project_endpoint,
        credential=_get_credential(),
    )
    # Responses API requires 2025-03-01-preview or later.
    kwargs = {"api_version": "2025-03-01-preview"}
    if agent_name:
        kwargs["agent_name"] = agent_name
    return client.get_openai_client(**kwargs)


def _extract_citations(resp: Any) -> list[dict]:
    """Pull citation annotations from a Responses API response, best-effort."""
    out: list[dict] = []
    try:
        for item in (getattr(resp, "output", None) or []):
            for block in (getattr(item, "content", None) or []):
                for ann in (getattr(block, "annotations", None) or []):
                    get = (lambda k: getattr(ann, k, None) if not isinstance(ann, dict) else ann.get(k))
                    url, title = get("url"), (get("title") or get("filename") or get("source_name"))
                    if url or title:
                        out.append({"title": title, "url": url})
    except Exception:
        pass
    return out


def _build_responses_api_input(messages: list[dict]) -> list[dict]:
    """Convert messages list into Responses API input format."""
    out = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            # Responses API uses 'system' role in the input list
            out.insert(0, {"role": "system", "content": content})
        elif role in ("user", "assistant"):
            out.append({"role": role, "content": content})
    return out if out else [{"role": "user", "content": str(messages)}]


async def call_grounded_agent(
    agent_role: str,
    messages: list[dict],
    run_id: Optional[str] = None,
) -> Optional[Any]:
    """Call a grounded agent via the Azure AI Foundry Responses API.

    The Responses API is called with the agent's full message context (system prompt
    + user content). The model runs inside Foundry's inference plane — usage is
    visible in the portal under Monitoring → Responses.

    Returns an AgentResult on success, None on any failure (caller falls back to
    the existing BaseAgent path).

    agent_role: one of 'curator', 'critic', 'assessment'
    """
    from backend.core.agent import AgentResult

    if agent_role not in GROUNDED_AGENT_NAMES:
        return None

    agent_name = GROUNDED_AGENT_NAMES[agent_role]

    try:
        import asyncio
        from config.settings import get_settings
        s = get_settings()

        # Bind client to agent-specific endpoint so KB, instructions, and tools are used.
        openai_client = await asyncio.to_thread(_get_openai_client, agent_name)
        api_input = _build_responses_api_input(messages)

        def _call():
            return openai_client.responses.create(
                model=s.azure_ai_model_deployment or "gpt-4.1",
                input=api_input,
            )

        resp = await asyncio.to_thread(_call)

        answer = getattr(resp, "output_text", None) or ""
        if not answer:
            for item in (getattr(resp, "output", None) or []):
                for block in (getattr(item, "content", None) or []):
                    answer += getattr(block, "text", "") or ""

        citations = _extract_citations(resp)
        if citations:
            citation_lines = "\n".join(
                f"  - {c.get('title', 'source')}: {c.get('url', '')}" for c in citations
            )
            answer = f"{answer}\n\nCitations (Foundry IQ):\n{citation_lines}"

        logger.info(
            "Foundry Responses API: agent=%s run=%s citations=%d chars=%d",
            agent_name, run_id or "?", len(citations), len(answer),
        )

        return AgentResult(
            agent_name=agent_role,
            content=answer,
            parsed=None,
            tool_calls_made=[{"tool": "foundry_responses_api", "agent": agent_name}],
            token_usage={},
        )

    except Exception as e:
        logger.warning(
            "Foundry Responses API call failed for %s (run=%s), falling back to BaseAgent: %s",
            agent_name, run_id or "?", e,
        )
        return None
