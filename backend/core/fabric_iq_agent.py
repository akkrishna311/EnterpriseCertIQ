"""Invoke the Foundry agent that has the Fabric IQ (OneLake Catalog) tool — On-Behalf-Of
the signed-in user.

Fabric IQ requires **user-delegated** auth; service principals are rejected. So this does NOT
use get_service_credential() — it wraps the end-user's Entra bearer token (forwarded from the
browser) and calls the agent via the v2 Responses API with an agent_reference. The Foundry Agent
Service then exchanges the user's token for the Fabric audience and runs the tool as that user.

Requires azure-ai-projects>=2.1.0 (for get_openai_client + responses). Validated against the
Foundry/Fabric docs (OBO flow, agent_reference, output_text, citations).
"""
from __future__ import annotations

import re
import time
from typing import Any

from config.settings import get_settings


def fabric_iq_ready() -> bool:
    """True when the OBO Fabric IQ path is configured (used for /health + UI gating)."""
    s = get_settings()
    return bool(s.azure_ai_project_endpoint and s.fabric_iq_agent_name)


class _StaticUserCredential:
    """A TokenCredential that returns a fixed user bearer token (OBO passthrough).

    The token must be minted by the frontend (MSAL) for the Foundry/AI audience; the Agent
    Service exchanges it to the Fabric audience (https://analysis.windows.net/powerbi/api).
    """

    def __init__(self, user_token: str, expires_on: int | None = None):
        self._token = user_token
        self._exp = expires_on or (int(time.time()) + 3000)

    def get_token(self, *scopes: str, **kwargs: Any):
        from azure.core.credentials import AccessToken
        return AccessToken(self._token, self._exp)


def _extract_citations(resp: Any) -> list[dict]:
    """Pull citation docs (title/url to Fabric items) from the response, best-effort.

    Shape verified loosely against the Responses API output annotations — returns [] if the
    structure differs, so it never breaks the answer.
    """
    out: list[dict] = []
    try:
        for item in (getattr(resp, "output", None) or []):
            for block in (getattr(item, "content", None) or []):
                for ann in (getattr(block, "annotations", None) or []):
                    g = (lambda k: getattr(ann, k, None) if not isinstance(ann, dict) else ann.get(k))
                    url, title = g("url"), (g("title") or g("filename"))
                    if url or title:
                        out.append({"title": title, "url": url})
    except Exception:
        pass
    return out


def _consent_link(text: str) -> str | None:
    """Detect a CONSENT_REQUIRED challenge (Managed OAuth first-use) and return its URL."""
    if "consent" not in text.lower():
        return None
    m = re.search(r"https?://\S+", text)
    return m.group(0).rstrip(".,)\"'") if m else None


def ask_fabric_iq(question: str, user_token: str) -> dict:
    """Ask the Fabric-IQ-tool agent a question OBO the signed-in user.

    Returns {answer, citations, consent_required, consent_link}. Raises RuntimeError for
    missing prerequisites (caller maps to HTTP errors).
    """
    s = get_settings()
    if not s.azure_ai_project_endpoint:
        raise RuntimeError("AZURE_AI_PROJECT_ENDPOINT is not set.")
    if not s.fabric_iq_agent_name:
        raise RuntimeError("FABRIC_IQ_AGENT_NAME is not set (the Foundry agent with the Fabric IQ tool).")
    if not user_token:
        raise RuntimeError("A signed-in user token is required (Fabric IQ rejects service principals).")

    try:
        from azure.ai.projects import AIProjectClient
    except ImportError as e:
        raise RuntimeError("azure-ai-projects is not installed.") from e

    client = AIProjectClient(
        endpoint=s.azure_ai_project_endpoint,
        credential=_StaticUserCredential(user_token),
    )
    if not hasattr(client, "get_openai_client"):
        raise RuntimeError(
            "azure-ai-projects>=2.1.0 required (get_openai_client/responses); install requirements.azure.txt."
        )

    openai_client = client.get_openai_client()
    try:
        resp = openai_client.responses.create(
            model=s.azure_ai_model_deployment or "gpt-4.1",
            input=question,
            extra_body={"agent_reference": {"name": s.fabric_iq_agent_name, "type": "agent_reference"}},
        )
    except Exception as e:                      # Managed OAuth first-use → CONSENT_REQUIRED
        link = _consent_link(str(e))
        if link:
            return {"answer": None, "citations": [], "consent_required": True, "consent_link": link}
        raise

    answer = getattr(resp, "output_text", None) or str(resp)
    # A response may itself carry a consent challenge instead of an answer.
    link = _consent_link(answer or "")
    if link:
        return {"answer": None, "citations": [], "consent_required": True, "consent_link": link}
    return {"answer": answer, "citations": _extract_citations(resp), "consent_required": False, "consent_link": None}
