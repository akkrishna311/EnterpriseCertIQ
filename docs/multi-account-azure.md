# Multi-Account / Multi-Tenant Azure

EnterpriseCertIQ can talk to Azure services that live in **different Azure accounts,
subscriptions, or tenants** at the same time — e.g. **Foundry in Account A, Fabric in
Account B**. There is no shared client, no ARM/subscription context, and no single
"current account": every service is reached by its **own endpoint + its own credential**.

## How auth works per service

| Service | Endpoint | Credential | Account isolation |
|---|---|---|---|
| Foundry model | `AZURE_AI_PROJECT_ENDPOINT` | `AZURE_AI_API_KEY` (key) or DefaultAzureCredential | key = any account |
| Foundry IQ (Search) | `FOUNDRY_IQ_ENDPOINT` | `AZURE_SEARCH_KEY` (key) | key = any account |
| Content Safety | `AZURE_CONTENT_SAFETY_ENDPOINT` | `AZURE_CONTENT_SAFETY_KEY` (key) | key = any account |
| Cosmos | `COSMOS_ENDPOINT` | `COSMOS_KEY` (key) | key = any account |
| Work IQ (Graph) | Microsoft Graph | its own Entra app token | own tenant/app |
| Key Vault | `AZURE_KEY_VAULT_URL` | `get_service_credential("keyvault")` | own SPN or shared |
| **Fabric IQ** | `FABRIC_IQ_ENDPOINT` | `get_service_credential("fabric")` — **dedicated SPN** | **own tenant** |

**Key-auth services are account-agnostic already** — an API key is self-contained, so pointing
Search/Content-Safety/Cosmos/Foundry at a different account is just a different endpoint + key.

**Identity-auth services** use the per-service credential factory
(`backend/core/azure_credentials.py`): if a service has a full service principal
(`{prefix}_tenant_id` + `{prefix}_client_id` + `{prefix}_client_secret`), it gets a
`ClientSecretCredential` scoped to **that** tenant; otherwise it shares
`DefaultAzureCredential`. This is what makes cross-tenant work — a single
`DefaultAzureCredential` can only ever be one tenant.

## Example: Foundry in Account A, Fabric in Account B

```dotenv
# ── Account A: Azure AI Foundry + Foundry IQ (key auth — no SPN needed) ──
MODEL_BACKEND=azure_foundry
AZURE_AI_PROJECT_ENDPOINT=https://hub-a.api.azureml.ms
AZURE_AI_API_KEY=<account-A-foundry-key>
FOUNDRY_IQ_ENDPOINT=https://search-a.search.windows.net
AZURE_SEARCH_KEY=<account-A-search-key>

# ── Account B: Fabric (Entra auth — its own service principal in tenant B) ──
FABRIC_IQ_ENDPOINT=https://<fabric-b-endpoint>
FABRIC_IQ_WORKSPACE=<workspace-in-account-B>
FABRIC_TENANT_ID=<tenant-B-guid>
FABRIC_CLIENT_ID=<spn-app-id-in-B>
FABRIC_CLIENT_SECRET=<spn-secret-in-B>
```

At runtime: the Foundry client uses Account A's key; the Fabric IQ Azure client calls
`get_service_credential("fabric")` → `ClientSecretCredential(tenant_id=B, …)`. The two never
share auth and never need to be in the same tenant.

### Set up the Fabric service principal (in Account B)

```bash
# signed in to Account B
az ad sp create-for-rbac --name eciq-fabric-reader
# → note appId (FABRIC_CLIENT_ID), password (FABRIC_CLIENT_SECRET), tenant (FABRIC_TENANT_ID)
```
Then grant that SPN access to the Fabric workspace/items in Account B (Fabric portal →
Workspace → Manage access → add the SPN as Viewer/Member as appropriate).

> Store `FABRIC_CLIENT_SECRET` in Key Vault (see docs/key-vault.md) rather than `.env` — the
> vault and the Fabric account can be different accounts; the vault is just a store.

## Status

- Key-based multi-account (Foundry / Search / Content Safety / Cosmos): **supported today**.
- Per-service credential factory + Fabric SPN config: **implemented**
  (`backend/core/azure_credentials.py`, `FABRIC_*` settings).
- Fabric IQ **Azure data binding itself** (OneLake/SQL queries) is still to be built — it runs
  as a local ontology today. When wired, it will call `get_service_credential("fabric")`, so
  the cross-account auth is already in place. See migration doc Phase 5.

## Adding a dedicated SPN to any other service

The factory is generic. To give, say, Key Vault its own account, add
`keyvault_tenant_id` / `keyvault_client_id` / `keyvault_client_secret` settings — the
existing `get_service_credential("keyvault")` call picks them up automatically.
