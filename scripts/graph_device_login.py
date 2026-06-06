"""
One-time Microsoft Graph device-code login for the real Work IQ source.

Acquires a delegated `Calendars.Read` token via the device-code flow and prints it.
The azure-identity token cache is persisted, so subsequent runs (and the backend's
DeviceCodeCredential) refresh silently without re-prompting.

Usage:
    export GRAPH_TENANT_ID=<tenant-guid>      # or "common"
    export GRAPH_CLIENT_ID=<app-registration-client-id>
    python scripts/graph_device_login.py

Then either:
  - export GRAPH_ACCESS_TOKEN=<printed token>   (quickest), or
  - leave the cache in place and set WORK_IQ_SOURCE=graph — the backend will reuse it.

Prereqs: pip install -r requirements.azure.txt  (provides azure-identity)
See docs/work-iq-graph.md for the full Entra app setup.
"""
import os
import sys


def main() -> int:
    tenant = os.environ.get("GRAPH_TENANT_ID", "common")
    client_id = os.environ.get("GRAPH_CLIENT_ID", "")
    if not client_id:
        print("ERROR: set GRAPH_CLIENT_ID (your Entra app registration client id).")
        return 1

    try:
        from azure.identity import DeviceCodeCredential, TokenCachePersistenceOptions
    except ImportError:
        print("ERROR: azure-identity not installed. Run: pip install -r requirements.azure.txt")
        return 1

    cred = DeviceCodeCredential(
        tenant_id=tenant,
        client_id=client_id,
        cache_persistence_options=TokenCachePersistenceOptions(name="enterprisecertiq-graph"),
        prompt_callback=lambda verification_uri, user_code, _: print(
            f"\n  1. Open {verification_uri}\n  2. Enter code: {user_code}\n"
        ),
    )
    token = cred.get_token("https://graph.microsoft.com/Calendars.Read")
    print("\n✅ Token acquired (cache persisted). Export it for the quickest path:\n")
    print(f"export GRAPH_ACCESS_TOKEN={token.token}\n")
    print("Or set WORK_IQ_SOURCE=graph and the backend will reuse the cached credential.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
