from __future__ import annotations

import os
from enum import Enum
from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelBackend(str, Enum):
    FOUNDRY_LOCAL = "foundry_local"
    AZURE_FOUNDRY = "azure_foundry"


class StorageBackend(str, Enum):
    LOCAL = "local"
    COSMOS = "cosmos"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env.azure", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=("settings_",),
    )

    # ── App ──────────────────────────────────────────────────────────
    app_name: str = "EnterpriseCertIQ"
    log_level: str = "INFO"
    backend_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # ── Backend toggle ────────────────────────────────────────────────
    model_backend: ModelBackend = ModelBackend.FOUNDRY_LOCAL
    storage_backend: StorageBackend = StorageBackend.LOCAL

    # ── Foundry Local ─────────────────────────────────────────────────
    foundry_local_endpoint: str = "http://localhost:5273/v1"
    foundry_local_model_alias: str = "phi-4-mini"
    foundry_local_reasoning_alias: str = ""  # falls back to model_alias if empty

    # ── Azure AI Foundry (cloud backend) ─────────────────────────────
    # Get this from: AI Foundry portal → your project → Settings → Project details
    azure_ai_project_endpoint: str = ""  # e.g. https://<hub>.api.azureml.ms (azure-ai-projects/agents)
    # OpenAI-compatible v1 endpoint, e.g. https://<res>.openai.azure.com/openai/v1
    # When set (azure_foundry mode), inference uses the OpenAI SDK against this — most reliable.
    azure_openai_endpoint: str = ""
    azure_ai_api_key: str = ""           # Leave empty to use DefaultAzureCredential
    azure_ai_api_version: str = "2024-12-01-preview"
    azure_ai_model_deployment: str = "gpt-4o"          # deployment name in your project
    azure_ai_reasoning_deployment: str = "gpt-4o"      # can use same or a different deployment
    azure_use_managed_identity: bool = False            # True = use DefaultAzureCredential

    # ── Cosmos DB ─────────────────────────────────────────────────────
    cosmos_endpoint: str = ""
    cosmos_key: str = ""
    cosmos_database: str = "enterprisecertiq"

    # ── Foundry IQ ────────────────────────────────────────────────────
    # Local: keyword search over ./backend/data/documents/
    # Azure: set to your Azure AI Search endpoint
    foundry_iq_endpoint: str = "local"
    foundry_iq_index_name: str = "cert-knowledge-base"
    # Dedicated Search admin key — separate from the Foundry model key
    azure_search_key: str = ""
    # Foundry portal → Settings → Connections → Name of your Azure AI Search connection.
    # When set, agents are registered with AzureAISearchTool (native Foundry IQ grounding).
    # Leave empty to use the direct httpx fallback path.
    foundry_search_connection_name: str = ""
    # When true (and MODEL_BACKEND=azure_foundry), the curator, critic, and assessment agents
    # are called via the Foundry Responses API with agent_reference so knowledge-base
    # retrieval and citation injection happen server-side. Falls back to BaseAgent on any error.
    foundry_use_responses_api: bool = False
    # When false (default), agents are pre-registered by register_agents_cloud_shell.py and
    # the startup registration is skipped. Set true only for auto-registration in environments
    # where the registration script has not been run (e.g. fresh judge installs).
    foundry_auto_register: bool = False

    # ── Work IQ source ────────────────────────────────────────────────
    # synthetic (default): work signals from learners.json
    # graph:               real Microsoft 365 calendar via Microsoft Graph
    #                      (Calendars.Read). Work IQ proper needs an M365 Copilot
    #                      add-on + preview enrolment; Graph delivers the same
    #                      WorkIQSignals on any M365 license. Falls back to
    #                      synthetic if a token/UPN is unavailable at call time.
    work_iq_source: str = "synthetic"  # synthetic | graph
    graph_tenant_id: str = ""
    graph_client_id: str = ""
    graph_access_token: str = ""        # optional: paste a token to skip device-code
    graph_default_upn: str = "me"       # mailbox to read when no per-learner mapping
    graph_learner_upn_map: str = ""     # optional JSON: {"L-1004": "alex@contoso.com"}

    # ── Fabric IQ (semantic layer) ────────────────────────────────────
    # Local: in-memory ontology built from ./backend/data/synthetic/*.json
    # Azure: point at a Microsoft Fabric semantic model / OneLake endpoint.
    #        Not provisioned in this repo yet — see Phase 5 of the migration doc.
    fabric_iq_endpoint: str = "local"
    fabric_iq_workspace: str = ""  # Fabric workspace / lakehouse name (Azure mode)
    # SKU-free path: the Lakehouse SQL analytics endpoint (works on the Fabric Trial —
    # no data-agent / paid F2 needed). From Lakehouse → Settings → SQL analytics endpoint.
    # fabric_sql_endpoint = the TDS server (e.g. <id>.datawarehouse.fabric.microsoft.com),
    # fabric_sql_database = the lakehouse name.
    fabric_sql_endpoint: str = ""
    fabric_sql_database: str = ""
    # The Foundry agent (created in the portal) that has the Fabric IQ (OneLake Catalog)
    # tool attached to your Ontology. The app invokes THIS agent On-Behalf-Of the signed-in
    # user (Fabric IQ rejects service principals). Needs azure-ai-projects>=2.1.0.
    fabric_iq_agent_name: str = ""
    # Fabric can live in a DIFFERENT Azure account/tenant than Foundry. Give it its
    # own service principal (Entra app) — Fabric is Entra-auth, not key-auth. When
    # all three are set, the Fabric IQ client uses a ClientSecretCredential scoped to
    # that tenant; otherwise it falls back to DefaultAzureCredential.
    fabric_tenant_id: str = ""
    fabric_client_id: str = ""
    fabric_client_secret: str = ""

    # ── MCP ───────────────────────────────────────────────────────────
    ms_learn_mcp_url: str = "https://learn.microsoft.com/api/mcp"
    own_mcp_port: int = 8001

    # ── Telemetry ─────────────────────────────────────────────────────
    # false (default): spans created but not exported (zero overhead locally)
    # true + local:    console exporter (verbose, for debugging)
    # true + azure:    Azure Monitor exporter (requires connection string below)
    enable_telemetry: bool = False
    # From Azure portal: Application Insights → Connection String
    applicationinsights_connection_string: str = ""

    # ── Audio briefing (Azure AI Speech TTS) ──────────────────────────
    # Grounded two-host "audio study briefing". Synthesis uses Azure AI Speech
    # (key-based → can live in its own account). Transcript works with no key;
    # audio synthesis requires speech_key + speech_region.
    enable_audio: bool = True
    speech_key: str = ""
    speech_region: str = ""            # e.g. eastus
    audio_locale: str = "en-US"
    audio_voice_host_a: str = "en-US-AvaNeural"
    audio_voice_host_b: str = "en-US-AndrewNeural"

    # ── Azure Key Vault (secret store) ────────────────────────────────
    # When set, the backend loads secrets from this vault at startup and
    # overrides the matching settings (KV is the source of truth in cloud).
    # Empty (default) → secrets come from env/.env as before. Auth uses
    # DefaultAzureCredential (az login locally / managed identity in Azure).
    azure_key_vault_url: str = ""  # e.g. https://enterprisecertiq-kv.vault.azure.net

    # ── Deterministic agent fallback (3rd tier) ───────────────────────
    # auto (default): if a model call fails, the agent falls back to a
    #                 deterministic builder so the pipeline never breaks.
    # force:          skip the model entirely — fully deterministic demo mode
    #                 (zero credentials, instant, reproducible).
    # off:            never fall back; surface model errors.
    agent_fallback_mode: str = "auto"  # auto | force | off

    # ── LLM response cache ────────────────────────────────────────────
    # SHA-256 keyed cache over (model, messages, tools, temperature). A cache
    # hit skips the model call entirely — cuts cost + latency and makes demos
    # instant + deterministic. Disable for a true cold run.
    enable_llm_cache: bool = True
    llm_cache_max_entries: int = 2000

    # ── Azure AI Content Safety (RAI guardrail) ───────────────────────
    # When endpoint + key are set, free-text agent output is screened by the
    # live Content Safety API (Hate/SelfHarm/Sexual/Violence). severity >=
    # threshold → BLOCK. Falls back to the regex guard when unconfigured.
    azure_content_safety_endpoint: str = ""
    azure_content_safety_key: str = ""
    azure_content_safety_threshold: int = 2  # 0..6 (Azure severity scale)

    # ── Hosted agent env var aliases ──────────────────────────────────
    # The Foundry platform reserves ALL FOUNDRY_* and AGENT_* prefixes, so
    # deploy_hosted_agent.py injects these as ECIQ_* instead.  Accept both so
    # local .env.local (FOUNDRY_*) and the hosted container (ECIQ_*) work.
    @model_validator(mode="after")
    def _apply_eciq_overrides(self) -> "Settings":
        eciq_endpoint = os.environ.get("ECIQ_IQ_ENDPOINT")
        if eciq_endpoint:
            self.foundry_iq_endpoint = eciq_endpoint
        eciq_index = os.environ.get("ECIQ_IQ_INDEX_NAME")
        if eciq_index:
            self.foundry_iq_index_name = eciq_index
        eciq_responses = os.environ.get("ECIQ_USE_RESPONSES_API")
        if eciq_responses is not None:
            self.foundry_use_responses_api = eciq_responses.lower() in ("true", "1", "yes")
        return self

    # ── Derived helpers ───────────────────────────────────────────────
    @computed_field
    @property
    def is_local(self) -> bool:
        return self.model_backend == ModelBackend.FOUNDRY_LOCAL

    @computed_field
    @property
    def active_endpoint(self) -> str:
        if self.is_local:
            return self.foundry_local_endpoint
        return self.azure_ai_project_endpoint

    @computed_field
    @property
    def active_model(self) -> str:
        if self.is_local:
            return self.foundry_local_model_alias
        return self.azure_ai_model_deployment

    @computed_field
    @property
    def active_reasoning_model(self) -> str:
        if self.is_local:
            return self.foundry_local_reasoning_alias or self.foundry_local_model_alias
        return self.azure_ai_reasoning_deployment

    @computed_field
    @property
    def active_api_key(self) -> str:
        if self.is_local:
            return "not-required"
        return self.azure_ai_api_key  # empty string → use DefaultAzureCredential

    @computed_field
    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @computed_field
    @property
    def own_mcp_url(self) -> str:
        return f"http://localhost:{self.own_mcp_port}"

    @computed_field
    @property
    def data_dir(self) -> str:
        return os.path.join(os.path.dirname(__file__), "..", "backend", "data")

    @computed_field
    @property
    def store_dir(self) -> str:
        path = os.path.join(os.path.dirname(__file__), "..", "backend", "data", "store")
        os.makedirs(path, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
