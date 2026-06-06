# Azure Key Vault — Secret Management

Move all secrets out of `.env` into Azure Key Vault. The backend loads them at startup
and overrides the matching settings; no plaintext keys in env or code.

## What's already wired (code side — done)

| Piece | File |
|---|---|
| Setting | `AZURE_KEY_VAULT_URL` in `config/settings.py` |
| Loader | `config/key_vault.py` — `load_key_vault_secrets()` (DefaultAzureCredential) |
| Startup hook | `backend/main.py` lifespan calls it before telemetry/model/search |
| Push script | `scripts/push_secrets_to_keyvault.py` |
| Health | `/health` reports `key_vault: configured|off` |

Secrets the app reads from the vault (hyphenated names → settings field):

| Key Vault secret | Settings field |
|---|---|
| `azure-ai-api-key` | `AZURE_AI_API_KEY` |
| `azure-search-key` | `AZURE_SEARCH_KEY` |
| `azure-content-safety-key` | `AZURE_CONTENT_SAFETY_KEY` |
| `cosmos-key` | `COSMOS_KEY` |
| `graph-access-token` | `GRAPH_ACCESS_TOKEN` |
| `appinsights-connection-string` | `APPLICATIONINSIGHTS_CONNECTION_STRING` |

When `AZURE_KEY_VAULT_URL` is empty, nothing changes — secrets come from `.env` as today.
So local dev and CI stay offline; the vault is opt-in.

## What YOU do (needs your Azure subscription — I can't from here)

> The Azure CLI isn't available in the build environment, so the vault must be created and
> the secrets pushed by you. After that the app is one env-var away from using it.

### Step 1 — Create the vault (portal or CLI)

**Portal:** Create a resource → **Key Vault** → same resource group/region as the app →
Permission model: **Azure role-based access control (RBAC)** → Create.

**CLI (equivalent):**
```bash
RG=enterprisecertiq-rg
az keyvault create -g $RG -n enterprisecertiq-kv \
  --enable-rbac-authorization true
VAULT_URL=$(az keyvault show -g $RG -n enterprisecertiq-kv --query properties.vaultUri -o tsv)
echo $VAULT_URL    # → https://enterprisecertiq-kv.vault.azure.net/
```

### Step 2 — Grant yourself permission to write secrets

```bash
ME=$(az ad signed-in-user show --query id -o tsv)
SCOPE=$(az keyvault show -g $RG -n enterprisecertiq-kv --query id -o tsv)
az role assignment create --assignee $ME \
  --role "Key Vault Secrets Officer" --scope $SCOPE
```
(Portal: Key Vault → Access control (IAM) → Add role assignment → *Key Vault Secrets Officer* → your user.)

### Step 3 — Push your current secrets into the vault (one command)

```bash
source .venv/bin/activate
pip install -r requirements.azure.txt        # includes azure-keyvault-secrets
az login                                       # DefaultAzureCredential uses this
export AZURE_KEY_VAULT_URL=$VAULT_URL
python scripts/push_secrets_to_keyvault.py     # reads .env, writes non-empty secrets
```
This reads `AZURE_SEARCH_KEY`, `AZURE_AI_API_KEY`, etc. from your `.env`/env and stores them
in the vault. (Or set each manually: `az keyvault secret set --vault-name enterprisecertiq-kv --name azure-search-key --value <key>`.)

### Step 4 — Run the app against the vault

Local:
```bash
# keep az login active so DefaultAzureCredential can read the vault
export AZURE_KEY_VAULT_URL=https://enterprisecertiq-kv.vault.azure.net
# remove the plaintext keys from .env.local now that the vault holds them
./start.sh --no-setup --skip-model
curl -s localhost:8000/health | python3 -m json.tool | grep key_vault   # → "configured"
# logs show: "Key Vault: N secret(s) loaded"
```

Azure Container Apps (production — no secrets in env at all):
```bash
# 1. give the app a managed identity
az containerapp identity assign -g $RG -n eciq-backend --system-assigned
PRINCIPAL=$(az containerapp identity show -g $RG -n eciq-backend --query principalId -o tsv)
# 2. let it READ secrets
az role assignment create --assignee $PRINCIPAL \
  --role "Key Vault Secrets User" --scope $SCOPE
# 3. point the app at the vault and drop the secret env vars
az containerapp update -g $RG -n eciq-backend \
  --set-env-vars AZURE_KEY_VAULT_URL=https://enterprisecertiq-kv.vault.azure.net
```
The managed identity reads the vault at startup via `DefaultAzureCredential` — no keys are
ever set as container env vars.

## Rotation

Rotate a key in its source service (e.g. regenerate the Search admin key), then:
```bash
az keyvault secret set --vault-name enterprisecertiq-kv --name azure-search-key --value <new>
# restart the app (or it picks it up on next startup)
```
No code or container env changes needed — the vault is the single source of truth.

## Notes

- `DefaultAzureCredential` resolves: env service principal → managed identity → `az login`.
  Locally you need `az login`; in Azure the managed identity covers it.
- Loading never breaks startup: a missing secret is skipped, a vault error is logged and the
  app falls back to whatever env values exist.
- Key Vault names allow only letters, digits, and hyphens — hence `azure-search-key`, not
  `AZURE_SEARCH_KEY`. The mapping lives in `config/key_vault.SECRET_MAP`.
