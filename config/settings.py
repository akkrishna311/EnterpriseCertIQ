from __future__ import annotations

import os
from enum import Enum
from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
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
    azure_ai_project_endpoint: str = ""  # e.g. https://<hub>.api.azureml.ms
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
    # Azure: set to your Foundry project endpoint (same as azure_ai_project_endpoint)
    foundry_iq_endpoint: str = "local"
    foundry_iq_index_name: str = "cert-knowledge-base"

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
