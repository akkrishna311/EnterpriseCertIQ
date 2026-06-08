"""
Model client factory.

LOCAL  → Foundry Local  (openai.AsyncOpenAI  → localhost:5273/v1)
CLOUD  → Azure AI Foundry (azure-ai-inference ChatCompletionsClient,
          wrapped in a thin adapter so BaseAgent sees the same interface)

Auth options for Azure AI Foundry (set in .env.local):
  API key:          AZURE_AI_API_KEY=<key>
  Managed identity: AZURE_USE_MANAGED_IDENTITY=true  (leave AZURE_AI_API_KEY empty)
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any, Optional

from config.settings import ModelBackend, get_settings

logger = logging.getLogger(__name__)


# ── Foundry Local path (pure OpenAI-compatible) ───────────────────────────

def _make_local_client():
    from openai import AsyncOpenAI
    s = get_settings()
    logger.info("Client: Foundry Local → %s", s.foundry_local_endpoint)
    return AsyncOpenAI(base_url=s.foundry_local_endpoint, api_key="not-required")


# ── Azure AI Foundry adapter ──────────────────────────────────────────────
#
# azure-ai-inference ChatCompletionsClient uses:
#   response = await client.complete(model=..., messages=..., tools=...)
#
# BaseAgent expects the OpenAI interface:
#   response = await client.chat.completions.create(model=..., ...)
#
# The adapter below makes the Foundry client quack like an OpenAI client.
# Response objects are identical in structure (choices[0].message, usage, etc.)

class _FoundryCompletions:
    """Translates openai-style `.create(**kwargs)` → Foundry `.complete(**kwargs)`."""

    def __init__(self, foundry_client):
        self._client = foundry_client

    async def create(self, **kwargs) -> Any:
        from azure.ai.inference.models import (
            ChatRequestMessage,
            SystemMessage,
            UserMessage,
            AssistantMessage,
            ToolMessage,
        )

        # Convert message dicts → azure-ai-inference message objects
        raw_msgs = kwargs.pop("messages", [])
        converted = []
        for m in raw_msgs:
            role = m.get("role", "user")
            content = m.get("content") or ""
            tool_calls = m.get("tool_calls")
            tool_call_id = m.get("tool_call_id")

            if role == "system":
                converted.append(SystemMessage(content=content))
            elif role == "user":
                converted.append(UserMessage(content=content))
            elif role == "assistant":
                if tool_calls:
                    # Reconstruct AssistantMessage with tool_calls
                    converted.append(AssistantMessage(
                        content=content,
                        tool_calls=[
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["function"]["name"],
                                    "arguments": tc["function"]["arguments"],
                                },
                            }
                            for tc in tool_calls
                        ],
                    ))
                else:
                    converted.append(AssistantMessage(content=content))
            elif role == "tool":
                converted.append(ToolMessage(
                    tool_call_id=tool_call_id or "",
                    content=content,
                ))
            else:
                converted.append(UserMessage(content=content))

        # Tools: pass through as-is (Foundry accepts OpenAI tool format)
        foundry_kwargs: dict = {"messages": converted}
        for key in ("model", "temperature", "max_tokens", "tools", "tool_choice"):
            if key in kwargs:
                foundry_kwargs[key] = kwargs[key]

        return await self._client.complete(**foundry_kwargs)


class _FoundryChatCompletions:
    def __init__(self, foundry_client):
        self.completions = _FoundryCompletions(foundry_client)


class FoundryClientAdapter:
    """Drop-in replacement for openai.AsyncOpenAI — wraps azure-ai-inference."""

    def __init__(self, foundry_client):
        self.chat = _FoundryChatCompletions(foundry_client)


def _make_foundry_client(role: str = "default") -> FoundryClientAdapter:
    from azure.ai.inference.aio import ChatCompletionsClient
    from azure.core.credentials import AzureKeyCredential

    s = get_settings()

    if not s.azure_ai_project_endpoint:
        raise RuntimeError(
            "MODEL_BACKEND=azure_foundry but AZURE_AI_PROJECT_ENDPOINT is not set.\n"
            "Get it from: AI Foundry portal → your project → Settings → Project details.\n"
            "Set it in .env.local:  AZURE_AI_PROJECT_ENDPOINT=https://<hub>.api.azureml.ms"
        )

    # Auth: API key or DefaultAzureCredential (managed identity)
    if s.azure_use_managed_identity or not s.azure_ai_api_key:
        from azure.identity.aio import DefaultAzureCredential
        credential = DefaultAzureCredential()
        logger.info("Client: Azure AI Foundry (managed identity) → %s", s.azure_ai_project_endpoint)
    else:
        credential = AzureKeyCredential(s.azure_ai_api_key)
        logger.info("Client: Azure AI Foundry (API key) → %s", s.azure_ai_project_endpoint)

    # The Foundry inference endpoint for chat completions:
    # https://<hub>.api.azureml.ms  (models are addressed by deployment name in each call)
    foundry_client = ChatCompletionsClient(
        endpoint=s.azure_ai_project_endpoint,
        credential=credential,
        api_version=s.azure_ai_api_version,
    )
    return FoundryClientAdapter(foundry_client)


# ── Public API ─────────────────────────────────────────────────────────────

def _needs_max_completion_tokens(model: str) -> bool:
    """gpt-5 family and o-series reasoning models reject `max_tokens` and require
    `max_completion_tokens`. gpt-4.x / gpt-4o still use `max_tokens`."""
    m = (model or "").lower()
    return m.startswith(("gpt-5", "o1", "o3", "o4"))


class _V1Completions:
    """Translates request params for models with newer constraints, then delegates."""
    def __init__(self, client):
        self._client = client

    async def create(self, **kwargs):
        model = kwargs.get("model", "")
        if _needs_max_completion_tokens(model) and "max_tokens" in kwargs:
            kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
        return await self._client.chat.completions.create(**kwargs)


class _V1Chat:
    def __init__(self, client):
        self.completions = _V1Completions(client)


class _AzureOpenAIV1Adapter:
    """openai.AsyncOpenAI wrapper that adapts params per model (e.g. gpt-5 →
    max_completion_tokens). Delegates everything else to the real client."""
    def __init__(self, client):
        self._client = client
        self.chat = _V1Chat(client)

    def __getattr__(self, name):
        return getattr(self._client, name)


def _make_azure_openai_client():
    """Azure AI Foundry's OpenAI-compatible v1 endpoint via the OpenAI SDK.

    The newer *.services.ai.azure.com / *.openai.azure.com resources expose an
    OpenAI-compatible surface at `<resource>.openai.azure.com/openai/v1`. Pointing
    openai.AsyncOpenAI at it is the most reliable path — identical interface to the
    Foundry Local client, so BaseAgent is unchanged. Wrapped so gpt-5 / o-series
    deployments get `max_completion_tokens` automatically.
    """
    from openai import AsyncOpenAI
    s = get_settings()
    logger.info("Client: Azure OpenAI v1 → %s", s.azure_openai_endpoint)
    return _AzureOpenAIV1Adapter(
        AsyncOpenAI(base_url=s.azure_openai_endpoint, api_key=s.azure_ai_api_key)
    )


@lru_cache(maxsize=4)
def get_client(role: str = "default"):
    """
    Returns a client for the active backend.
    - Foundry Local: openai.AsyncOpenAI (unchanged interface)
    - Azure OpenAI v1 endpoint (if AZURE_OPENAI_ENDPOINT set): openai.AsyncOpenAI
    - Azure AI Foundry project endpoint: FoundryClientAdapter (azure-ai-inference)
    """
    s = get_settings()
    if s.model_backend == ModelBackend.FOUNDRY_LOCAL:
        return _make_local_client()
    if s.azure_openai_endpoint:
        return _make_azure_openai_client()
    return _make_foundry_client(role)


def get_model_name(role: str = "default") -> str:
    """Returns the model deployment name for the given role."""
    s = get_settings()
    if role == "reasoning":
        return s.active_reasoning_model
    return s.active_model


@lru_cache(maxsize=8)
def ensure_model_loaded(role: str = "default") -> None:
    """Ensure the Foundry Local model for `role` is loaded — once per process.

    The model is normally loaded by the `setup_foundry.py --serve` manager that
    backs the :5273 endpoint. This is a best-effort safety net for the case
    where it isn't. Cached per role so it runs at most once per model per
    process — the SDK's `is_loaded` is unreliable, so without caching this could
    trigger a redundant (slow) reload on every agent call. No-op on Azure.
    """
    s = get_settings()
    if s.model_backend != ModelBackend.FOUNDRY_LOCAL:
        return
    alias = get_model_name(role)
    try:
        from foundry_local_sdk import FoundryLocalManager, Configuration
        if getattr(FoundryLocalManager, "instance", None) is None:
            FoundryLocalManager.initialize(Configuration(app_name="enterprisecertiq"))
        mgr = FoundryLocalManager.instance
        model = mgr.catalog.get_model(alias)
        if not model.is_loaded:
            logger.info("Foundry Local: loading model '%s' on demand", alias)
            model.load()
    except Exception as e:
        # Don't hard-fail the request path; the chat call will surface a clear
        # error if the model truly can't be served.
        logger.warning("ensure_model_loaded('%s') failed: %s", alias, e)


@lru_cache(maxsize=8)
def model_supports_tools(role: str = "default") -> bool:
    """Whether the model for `role` can accept OpenAI tool definitions.

    Azure deployments (gpt-4o etc.) support tools. For Foundry Local we probe
    the catalog — reasoning models such as phi-4-reasoning report
    supports_tool_calling=False, and sending them tools would 400.
    Defaults to False on any uncertainty so we never send tools to a model
    that can't handle them.
    """
    s = get_settings()
    if s.model_backend == ModelBackend.AZURE_FOUNDRY:
        return True
    alias = get_model_name(role)
    try:
        from foundry_local_sdk import FoundryLocalManager, Configuration
        # initialize() raises if the singleton already exists — only init once.
        if getattr(FoundryLocalManager, "instance", None) is None:
            FoundryLocalManager.initialize(Configuration(app_name="enterprisecertiq"))
        model = FoundryLocalManager.instance.catalog.get_model(alias)
        return bool(model.supports_tool_calling)
    except Exception as e:
        logger.warning("Could not probe tool support for '%s': %s", alias, e)
        return False
