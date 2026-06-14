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
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Foundry agent names for the 3 grounded agents (must match what's registered in portal)
GROUNDED_AGENT_NAMES = {
    "curator":    "eciq-learning-path-curator",
    "critic":     "eciq-readiness-critic",
    "assessment": "eciq-assessment-agent",
}

# JSON format hints appended to the user message so the Foundry agent's final
# answer is structured output, not prose.  The agent still calls knowledge_base_retrieve
# to ground its answer before generating this JSON.
_SCHEMA_HINTS: dict[str, str] = {
    "curator": (
        "\n\nIMPORTANT: Respond with valid JSON ONLY — a JSON array of topic objects. "
        "Each object must have exactly these fields: "
        "title (string), domain (string), hours (number 0.5-12), "
        "priority (\"high\"|\"medium\"|\"low\"), "
        "citations (array of objects with fields: doc_id, title, span_id, excerpt, source_url), "
        "ms_learn_url (string). "
        "No prose, no markdown, no explanation outside the JSON array."
    ),
    "critic": (
        "\n\nIMPORTANT: Respond with valid JSON ONLY — a single JSON object with these fields: "
        "objections (array of {objection_id, plan_element_id, "
        "severity (\"red\"|\"amber\"), description, recommendation, citation}), "
        "forecast (object with pass_probability, estimated_exam_score, pass_threshold, weakest_topic), "
        "domain_mastery (object mapping domain name to mastery score 0-1), "
        "overall_risk (\"low\"|\"medium\"|\"high\"), "
        "ai_disclosure (string). "
        "No prose, no markdown, no explanation outside the JSON object."
    ),
    "assessment": (
        "\n\nIMPORTANT: Respond with valid JSON ONLY — a single JSON object with these fields: "
        "learner_id (string), cert_id (string), "
        "readiness_verdict (\"ready\"|\"not_ready\"|\"insufficient_evidence\"), "
        "booking_verdict (\"GO\"|\"CONDITIONAL_GO\"|\"NOT_YET\"), "
        "pass_probability (number 0-1), estimated_exam_score (integer), pass_threshold (integer), "
        "weak_areas (string array), "
        "sample_questions (array of {question_text, domain, citation}), "
        "recommendation (\"advance\"|\"remediate\"|\"gather_evidence\"), "
        "next_step (string), rationale (string), ai_disclosure (string). "
        "No prose, no markdown, no explanation outside the JSON object."
    ),
}

# Pydantic models for validating the JSON the Foundry agent returns
def _get_response_schemas() -> dict[str, Any]:
    from backend.models import CuratedTopicList, CriticOutput, AssessmentOutput
    return {
        "curator": CuratedTopicList,
        "critic": CriticOutput,
        "assessment": AssessmentOutput,
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
    """Return DefaultAzureCredential for AIProjectClient.

    The agent-specific endpoint ({project_endpoint}/agents/{name}/endpoint/...)
    requires a real Entra Bearer token — API keys are rejected at that layer.
    DefaultAzureCredential resolves via: SPN env vars → managed identity (Azure)
    → az login (local dev). Secrets (API keys etc.) come from Key Vault at startup.
    """
    from backend.core.azure_credentials import get_service_credential
    return get_service_credential("foundry")


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
        allow_preview=True,  # required for get_openai_client(agent_name=...)
    )
    # When agent_name is set, get_openai_client returns a plain openai.OpenAI bound to
    # the agent endpoint URL — api_version is baked into that URL, not a constructor arg.
    # Without agent_name it returns AzureOpenAI where api_version would apply.
    if agent_name:
        return client.get_openai_client(agent_name=agent_name)
    return client.get_openai_client(api_version="2025-03-01-preview")


def _extract_json_payload(content: str) -> Any:
    """Extract and parse JSON from a text response (mirrors BaseAgent._extract_json_payload)."""
    if not content:
        return None
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", content, flags=re.IGNORECASE).strip()
    candidates = [cleaned, content.strip()]
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", cleaned)
    if match:
        candidates.insert(0, match.group(1).strip())
    for opener, closer in (("{", "}"), ("[", "]")):
        start = cleaned.find(opener)
        end = cleaned.rfind(closer)
        if 0 <= start < end:
            candidates.append(cleaned[start:end + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except Exception:
            continue
    return None


def _parse_structured(content: str, agent_role: str):
    """Try to parse the Foundry agent's text response as the expected Pydantic schema.

    Returns (json_str, parsed_model) on success, or (content, None) on failure.
    The parsed_model is a Pydantic instance matching the agent's response schema.
    """
    schemas = _get_response_schemas()
    schema_cls = schemas.get(agent_role)
    if schema_cls is None:
        return content, None

    payload = _extract_json_payload(content)
    if payload is None:
        return content, None

    try:
        parsed = schema_cls.model_validate(payload)
        serialized = json.dumps(
            parsed.model_dump(mode="json") if hasattr(parsed, "model_dump")
            else parsed.root if hasattr(parsed, "root")  # RootModel
            else payload,
            indent=2,
        )
        return serialized, parsed
    except Exception as exc:
        logger.debug("Foundry JSON parse failed for %s: %s", agent_role, exc)
        return content, None


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


def _build_responses_api_input(messages: list[dict], schema_hint: str = "") -> list[dict]:
    """Convert messages list into Responses API input format.

    When schema_hint is provided it is appended to the last user message so the
    Foundry agent knows to emit JSON (the agent still calls its KB tools first).
    """
    out = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            out.insert(0, {"role": "system", "content": content})
        elif role in ("user", "assistant"):
            out.append({"role": role, "content": content})

    if not out:
        out = [{"role": "user", "content": str(messages)}]

    # Append JSON schema hint to the last user message so the agent formats its
    # final answer as JSON after completing any KB retrieval tool calls.
    if schema_hint:
        for i in range(len(out) - 1, -1, -1):
            if out[i].get("role") == "user":
                out[i] = {**out[i], "content": out[i]["content"] + schema_hint}
                break

    return out


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

        # Inject JSON schema hint so the agent formats its final answer as structured
        # output (after completing KB retrieval).  This mirrors BaseAgent's response_format
        # constraint on the local path so downstream workflow.py parsing is identical.
        schema_hint = _SCHEMA_HINTS.get(agent_role, "")
        api_input = _build_responses_api_input(messages, schema_hint=schema_hint)

        def _call():
            return openai_client.responses.create(
                model=s.azure_ai_model_deployment or "gpt-4.1",
                input=api_input,
            )

        # Explicit OTel span so every KB-grounded agent call appears as a named
        # operation in App Insights (workflow.run → foundry_agent.call children).
        from backend.core.telemetry import span as _otel_span
        with _otel_span(
            "foundry_agent.call",
            agent=agent_name,
            role=agent_role,
            run_id=run_id or "?",
            kb_grounded="true",
        ):
            resp = await asyncio.to_thread(_call)

        answer = getattr(resp, "output_text", None) or ""
        if not answer:
            for item in (getattr(resp, "output", None) or []):
                for block in (getattr(item, "content", None) or []):
                    answer += getattr(block, "text", "") or ""

        citations = _extract_citations(resp)

        # Try to parse the JSON response and validate against the agent's Pydantic schema.
        # On success: content = canonical JSON, parsed = Pydantic model (same as local path).
        # On failure: fall back to raw text + appended citation block (degraded but functional).
        content, parsed_model = _parse_structured(answer, agent_role)

        if parsed_model is not None:
            logger.info(
                "foundry_agent.call agent=%s run=%s citations=%d chars=%d parsed=OK",
                agent_name, run_id or "?", len(citations), len(content),
            )
        else:
            # Parsed failed — append citation block to raw text for display
            if citations:
                citation_lines = "\n".join(
                    f"  - {c.get('title', 'source')}: {c.get('url', '')}" for c in citations
                )
                content = f"{content}\n\nCitations (Foundry IQ):\n{citation_lines}"
            logger.warning(
                "foundry_agent.call agent=%s run=%s citations=%d chars=%d parsed=FAILED",
                agent_name, run_id or "?", len(citations), len(content),
            )

        return AgentResult(
            agent_name=agent_role,
            content=content,
            parsed=parsed_model,
            tool_calls_made=[{"tool": "foundry_responses_api", "agent": agent_name}],
            token_usage={},
        )

    except Exception as e:
        logger.warning(
            "Foundry Responses API call failed for %s (run=%s), falling back to BaseAgent: %s",
            agent_name, run_id or "?", e,
        )
        return None
