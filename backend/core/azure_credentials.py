"""
Per-service Azure credential factory — enables multi-account / multi-tenant setups.

Each Azure service in this app is addressed by its own endpoint + its own secret, so
key-based services (Foundry model, Foundry IQ/Search, Content Safety, Cosmos) can already
live in *different* Azure accounts simply by setting each one's endpoint + key.

The wrinkle is **identity-based** auth: a single `DefaultAzureCredential` resolves to ONE
tenant. So when a service (e.g. **Fabric**, which is Entra-auth with no API key) lives in a
*different* account than the rest, it needs its own service principal.

`get_service_credential("fabric")` returns:
  - a `ClientSecretCredential` scoped to that service's tenant, if `{prefix}_tenant_id`,
    `{prefix}_client_id`, and `{prefix}_client_secret` are all set, else
  - a shared `DefaultAzureCredential` (az login / managed identity).

This lets "Foundry in account A, Fabric in account B" work cleanly: Foundry uses account A's
endpoint+key, Fabric uses its own SPN in tenant B — fully independent.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from config.settings import get_settings

logger = logging.getLogger(__name__)


def _in_azure() -> bool:
    """True when running inside Azure (Container Apps / App Service / VM) where a
    managed identity is reachable. Used to avoid the slow IMDS probe locally."""
    return bool(os.environ.get("IDENTITY_ENDPOINT") or os.environ.get("MSI_ENDPOINT"))


def _spn_fields(prefix: str) -> tuple[str, str, str]:
    s = get_settings()
    return (
        getattr(s, f"{prefix}_tenant_id", "") or "",
        getattr(s, f"{prefix}_client_id", "") or "",
        getattr(s, f"{prefix}_client_secret", "") or "",
    )


def has_dedicated_spn(prefix: str) -> bool:
    """True if a full service principal is configured for `prefix` (its own account)."""
    return all(_spn_fields(prefix))


def get_service_credential(prefix: str, is_async: bool = False) -> Any:
    """Return the right credential for a service.

    `prefix` is the settings prefix (e.g. "fabric", "keyvault", "foundry").
    `is_async=True` returns the azure.identity.aio variant for async SDK clients.
    """
    tenant_id, client_id, client_secret = _spn_fields(prefix)

    if tenant_id and client_id and client_secret:
        if is_async:
            from azure.identity.aio import ClientSecretCredential
        else:
            from azure.identity import ClientSecretCredential
        logger.info("Azure credential for '%s': dedicated service principal (tenant %s)",
                    prefix, tenant_id)
        return ClientSecretCredential(tenant_id=tenant_id, client_id=client_id,
                                      client_secret=client_secret)

    if is_async:
        from azure.identity.aio import DefaultAzureCredential
    else:
        from azure.identity import DefaultAzureCredential
    # Skip the managed-identity IMDS probe when not in Azure — it hangs locally
    # (the 169.254.169.254 endpoint only exists inside Azure).
    exclude_mi = not _in_azure()
    logger.debug("Azure credential for '%s': DefaultAzureCredential (exclude_managed_identity=%s)",
                 prefix, exclude_mi)
    return DefaultAzureCredential(exclude_managed_identity_credential=exclude_mi)
