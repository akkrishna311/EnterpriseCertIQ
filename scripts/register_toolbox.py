"""
Register EnterpriseCertIQ Foundry Toolbox.

Creates the eciq-governance-toolbox that bundles the 3 ECIQ skills so they
appear in the portal under each agent's Tools section and are auto-discoverable
via the MCP Resources protocol.

Run AFTER register_skills.py — skills must exist before the Toolbox references them.

Run BEFORE register_agents_cloud_shell.py — agents reference the Toolbox consumer URL.

Usage:
    python scripts/register_toolbox.py              # create/update toolbox
    python scripts/register_toolbox.py --dry-run    # print payload, no API call
    python scripts/register_toolbox.py --list       # list existing toolboxes

API:
    POST  {endpoint}/toolboxes/{name}/versions?api-version=v1
    PATCH {endpoint}/toolboxes/{name}/default_version?api-version=v1

Consumer endpoint wired into each agent as MCPTool (no project_connection_id needed):
    {endpoint}/toolboxes/eciq-governance-toolbox/mcp?api-version=v1
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

_API_VERSION = "v1"
TOOLBOX_NAME = "eciq-governance-toolbox"
TOOLBOX_DESCRIPTION = (
    "Foundry Skills governance bundle for all EnterpriseCertIQ agents — "
    "readiness rubric, citation policy, and safety escalation."
)
SKILLS = [
    "eciq-readiness-rubric",
    "eciq-citation-policy",
    "eciq-safety-escalation",
]


def _get_endpoint() -> str:
    try:
        from dotenv import load_dotenv
        load_dotenv(REPO_ROOT / ".env.local")
    except ImportError:
        pass
    endpoint = os.environ.get("AZURE_AI_PROJECT_ENDPOINT", "").rstrip("/")
    if not endpoint:
        print("[ERROR] AZURE_AI_PROJECT_ENDPOINT not set. Add it to .env.local or export it.")
        sys.exit(1)
    return endpoint


def _get_token() -> str:
    try:
        from azure.identity import DefaultAzureCredential
    except ImportError:
        print("[ERROR] azure-identity not installed. Run: pip install azure-identity")
        sys.exit(1)
    cred = DefaultAzureCredential()
    return cred.get_token("https://ai.azure.com/.default").token


def _toolbox_url(endpoint: str, *segments: str) -> str:
    base = f"{endpoint}/toolboxes/{TOOLBOX_NAME}"
    if segments:
        base += "/" + "/".join(segments)
    return f"{base}?api-version={_API_VERSION}"


def _api_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def register_toolbox(endpoint: str, token: str, dry_run: bool = False) -> bool:
    import urllib.request
    import urllib.error

    payload = {
        "name": TOOLBOX_NAME,
        "description": TOOLBOX_DESCRIPTION,
        "tools": [],
        "skills": [{"type": "skill_reference", "name": s} for s in SKILLS],
    }

    consumer_url = f"{endpoint}/toolboxes/{TOOLBOX_NAME}/mcp?api-version={_API_VERSION}"
    version_url = _toolbox_url(endpoint, "versions")

    print(f"\nToolbox: {TOOLBOX_NAME}")
    print(f"Skills:  {', '.join(SKILLS)}")

    if dry_run:
        print(f"\n[DRY RUN] Would POST to: {version_url}")
        print(f"  Payload:\n{json.dumps(payload, indent=4)}")
        print(f"\n  Consumer endpoint for agents:\n    {consumer_url}")
        return True

    print(f"\n  POST {version_url}")
    body_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        version_url, data=body_bytes, headers=_api_headers(token), method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read())
            version_id = (
                body.get("version_id")
                or body.get("id")
                or body.get("name")
                or "1"
            )
            print(f"  [OK] Version created: {version_id}")
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"  [ERROR] {e.code}: {err[:400]}")
        return False

    # Note: the Toolboxes API (v1 preview) does not expose a programmatic promote endpoint.
    # For a fresh install, v1 is automatically the default_version served by the consumer endpoint.

    print(f"\nToolbox consumer endpoint:")
    print(f"  {consumer_url}")
    print(
        "\nNext steps:\n"
        "  1. Run register_agents_cloud_shell.py to wire this Toolbox to all 9 agents.\n"
        "  2. Portal: Foundry ->project 'aipoc' ->Build ->Tools ->eciq-governance-toolbox\n"
        "  3. Portal: Foundry ->Agents -><agent> ->Tools — Toolbox should appear there."
    )
    return True


def list_toolboxes(endpoint: str, token: str) -> None:
    import urllib.request
    import urllib.error

    url = f"{endpoint}/toolboxes?api-version={_API_VERSION}"
    print(f"\nGET {url}")
    req = urllib.request.Request(url, headers=_api_headers(token), method="GET")
    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read())
            items = (
                body.get("value")
                or body.get("toolboxes")
                or (body if isinstance(body, list) else [])
            )
            if not items:
                print("  (no toolboxes found)")
            for t in items:
                name = t.get("name") or t.get("toolbox_name", "?")
                ver = t.get("default_version", "")
                print(f"  {name}  (default_version: {ver})")
    except urllib.error.HTTPError as e:
        print(f"  [ERROR] {e.code}: {e.read().decode()[:300]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Register EnterpriseCertIQ Foundry Toolbox")
    parser.add_argument("--dry-run", action="store_true", help="Print payload, no API call")
    parser.add_argument("--list", action="store_true", help="List existing toolboxes")
    args = parser.parse_args()

    endpoint = _get_endpoint()
    print(f"Project endpoint: {endpoint}")

    if args.dry_run:
        register_toolbox(endpoint, "dry-run-token", dry_run=True)
        return

    print("Acquiring Entra token (DefaultAzureCredential)...")
    token = _get_token()
    print("  [OK] Token acquired")

    if args.list:
        list_toolboxes(endpoint, token)
        return

    ok = register_toolbox(endpoint, token)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
