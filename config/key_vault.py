"""
Azure Key Vault secret loading.

When `AZURE_KEY_VAULT_URL` is set, the backend pulls secrets from the vault at
startup and overrides the matching settings (Key Vault is the source of truth in
cloud). When it's empty, nothing happens and secrets come from env/.env as before
— so local dev and CI stay offline and credential-free.

Auth uses `DefaultAzureCredential`, which resolves in this order:
  - environment service principal (AZURE_CLIENT_ID/SECRET/TENANT_ID),
  - managed identity (in Azure Container Apps / App Service),
  - `az login` (local developer).

Secret names in the vault use hyphens (Key Vault doesn't allow underscores) and
map to the snake_case settings field they populate — see `SECRET_MAP`.
"""
from __future__ import annotations

import logging
import os

from config.settings import get_settings

logger = logging.getLogger(__name__)

# Key Vault secret name  →  Settings attribute (and UPPER env var name).
SECRET_MAP: dict[str, str] = {
    "azure-ai-api-key": "azure_ai_api_key",
    "azure-search-key": "azure_search_key",
    "azure-content-safety-key": "azure_content_safety_key",
    "cosmos-key": "cosmos_key",
    "graph-access-token": "graph_access_token",
    "appinsights-connection-string": "applicationinsights_connection_string",
    "speech-key": "speech_key",
}


def load_key_vault_secrets() -> dict:
    """Fetch secrets from Key Vault and apply them to the live settings singleton.

    Mutates the cached `Settings` instance in place (so existing references see the
    new values) and mirrors them into `os.environ`. Safe to call unconditionally —
    no-ops when no vault URL is configured, and never raises (logs + returns instead),
    so a vault outage can't break startup.
    """
    s = get_settings()
    if not s.azure_key_vault_url:
        return {"enabled": False, "loaded": 0}

    try:
        from azure.keyvault.secrets import SecretClient
        from backend.core.azure_credentials import get_service_credential
    except ImportError:
        logger.warning("Key Vault: azure-keyvault-secrets not installed; "
                       "run `pip install -r requirements.azure.txt`")
        return {"enabled": True, "loaded": 0, "error": "sdk_missing"}

    try:
        # Uses a dedicated SPN if keyvault_* settings are set, else DefaultAzureCredential.
        client = SecretClient(vault_url=s.azure_key_vault_url,
                              credential=get_service_credential("keyvault"))
    except Exception as e:
        logger.warning("Key Vault: could not init client for %s: %s", s.azure_key_vault_url, e)
        return {"enabled": True, "loaded": 0, "error": str(e)}

    loaded: list[str] = []
    for kv_name, attr in SECRET_MAP.items():
        try:
            value = client.get_secret(kv_name).value
        except Exception as e:
            # Auth failure (e.g. no `az login` locally) → stop early instead of
            # retrying every secret; fall back to env values.
            if e.__class__.__name__ == "ClientAuthenticationError":
                logger.warning("Key Vault: auth unavailable (%s) — using env values", e.__class__.__name__)
                break
            continue  # this secret simply isn't in the vault — try the next
        if value:
            try:
                setattr(s, attr, value)
            except Exception as e:  # pragma: no cover - validation guard
                logger.warning("Key Vault: could not apply %s: %s", attr, e)
                continue
            os.environ[attr.upper()] = value
            loaded.append(kv_name)

    logger.info("Key Vault: loaded %d secret(s) from %s", len(loaded), s.azure_key_vault_url)
    return {"enabled": True, "loaded": len(loaded), "secrets": loaded}
