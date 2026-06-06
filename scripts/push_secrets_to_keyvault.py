"""
Push current secrets from the environment / .env into Azure Key Vault.

Run once after creating the vault and granting yourself the "Key Vault Secrets
Officer" role (see docs/key-vault.md). Idempotent — re-running updates values.

    export AZURE_KEY_VAULT_URL=https://<your-vault>.vault.azure.net
    az login                     # or set AZURE_CLIENT_ID/SECRET/TENANT_ID
    python scripts/push_secrets_to_keyvault.py

Reads every secret listed in config.key_vault.SECRET_MAP from settings and writes
the non-empty ones to the vault under their hyphenated names.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import get_settings
from config.key_vault import SECRET_MAP


def main() -> int:
    s = get_settings()
    if not s.azure_key_vault_url:
        print("ERROR: set AZURE_KEY_VAULT_URL (https://<vault>.vault.azure.net) first.")
        return 1

    try:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient
    except ImportError:
        print("ERROR: pip install -r requirements.azure.txt")
        return 1

    client = SecretClient(vault_url=s.azure_key_vault_url, credential=DefaultAzureCredential())
    print(f"Vault: {s.azure_key_vault_url}\n")

    pushed, skipped = 0, []
    for kv_name, attr in SECRET_MAP.items():
        value = getattr(s, attr, "")
        if not value:
            skipped.append(kv_name)
            continue
        client.set_secret(kv_name, value)
        print(f"  ✅ set {kv_name}  (from {attr.upper()})")
        pushed += 1

    if skipped:
        print(f"\n  skipped (empty in env): {', '.join(skipped)}")
    print(f"\nDone. Pushed {pushed} secret(s).")
    print("Now set AZURE_KEY_VAULT_URL in your runtime and the app loads them at startup.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
