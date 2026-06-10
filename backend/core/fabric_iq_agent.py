"""Invoke the Foundry agent that has the Fabric IQ (OneLake Catalog) tool — On-Behalf-Of
the signed-in user.

Fabric IQ requires **user-delegated** auth; service principals are rejected. So this does NOT
use get_service_credential() — it wraps the end-user's Entra bearer token (forwarded from the
browser) and calls the agent via the v2 Responses API with an agent_reference. The Foundry Agent
Service then exchanges the user's token for the Fabric audience and runs the tool as that user.

Requires azure-ai-projects>=2.1.0 (for get_openai_client + responses).
"""
from __future__ import annotations

import time
from typing import Any

from config.settings import get_settings


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


def ask_fabric_iq(question: str, user_token: str) -> str:
    """Ask the Fabric-IQ-tool agent a natural-language question, OBO the signed-in user.

    Raises with a clear message if prerequisites are missing (caller maps to HTTP errors).
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
    resp = openai_client.responses.create(
        model=s.azure_ai_model_deployment or "gpt-4.1",
        input=question,
        extra_body={"agent_reference": {"name": s.fabric_iq_agent_name, "type": "agent_reference"}},
    )
    return getattr(resp, "output_text", None) or str(resp)
