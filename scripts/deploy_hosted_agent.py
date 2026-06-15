"""
EnterpriseCertIQ — Deploy the orchestrator as a Foundry Hosted Agent.

Registers the container image (built by Dockerfile.hosted and pushed to ACR) with
Foundry Agent Service, polls until active, then prints the invocation endpoint.

Usage:
    python scripts/deploy_hosted_agent.py                  # deploy / update
    python scripts/deploy_hosted_agent.py --status         # check current status
    python scripts/deploy_hosted_agent.py --invoke "L-1004 AZ-204"  # test invoke
    python scripts/deploy_hosted_agent.py --delete         # remove the agent

Prerequisites:
    1. ACR created:  az acr create -g rg_genai -n eciqregistry --sku Basic --location eastus2 --admin-enabled true
    2. Image built:  az acr build -r eciqregistry -t enterprisecertiq-hosted:latest -f Dockerfile.hosted .
    3. ACR role:     az role assignment create --assignee <project-mi-object-id> \
                         --role "AcrPull" --scope /subscriptions/.../resourceGroups/rg_genai/providers/...
       (this script auto-assigns if you have Owner/UAMI rights — see --assign-acr-role)
    4. pip install "azure-ai-projects>=2.1.0" azure-identity

Run from project root:
    python scripts/deploy_hosted_agent.py
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
PROJECT_ENDPOINT = "https://<your-hub>.services.ai.azure.com/api/projects/<your-project>"
AGENT_NAME       = "eciq-orchestrator"
ACR_IMAGE        = "<your-acr>.azurecr.io/enterprisecertiq-hosted:latest"
ACR_NAME         = "<your-acr-name>"
RESOURCE_GROUP   = "<your-resource-group>"
SUBSCRIPTION_ID  = "<your-subscription-id>"
WORKSPACE_NAME   = "<your-foundry-workspace-name>"

# Environment variables injected into the hosted container.
# APPLICATIONINSIGHTS_CONNECTION_STRING is injected automatically by the platform.
# Note: no ${{connections.*}} refs here — the East US 2 project has no KB connection yet.
# The container starts up fine; IQ falls back to local keyword search mode.
AGENT_ENV_VARS = {
    "MODEL_BACKEND":               "azure_foundry",
    "AZURE_AI_PROJECT_ENDPOINT":   PROJECT_ENDPOINT,
    "AZURE_AI_MODEL_DEPLOYMENT":   "gpt-4.1",
    "ECIQ_USE_RESPONSES_API":      "false",
    "ECIQ_IQ_ENDPOINT":            "local",
    "ECIQ_IQ_INDEX_NAME":          "cert-knowledge-base",
    "ENABLE_TELEMETRY":            "false",
    "STORAGE_BACKEND":             "local",
    "LOG_LEVEL":                   "INFO",
}


def _get_client():
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential
    return AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential(),
        allow_preview=True,
    )


def _get_project_mi_object_id() -> str | None:
    """Return the object ID of the Foundry project's system-assigned managed identity."""
    try:
        import subprocess, json
        acr_scope = (
            f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}"
            f"/providers/Microsoft.ContainerRegistry/registries/{ACR_NAME}"
        )
        result = subprocess.run(
            ["az", "identity", "show",
             "--ids", f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}"
                      f"/providers/Microsoft.MachineLearningServices/workspaces/{WORKSPACE_NAME}",
             "--query", "principalId", "-o", "tsv"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def assign_acr_role() -> None:
    """Grant AcrPull on eciqregistry to the Foundry project managed identity."""
    import subprocess
    acr_scope = (
        f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}"
        f"/providers/Microsoft.ContainerRegistry/registries/{ACR_NAME}"
    )
    print("Assigning AcrPull role to Foundry project managed identity...")
    result = subprocess.run([
        "az", "role", "assignment", "create",
        "--assignee-object-id",
        # Get the project MI principal ID
        subprocess.run(
            ["az", "ml", "workspace", "show",
             "-g", RESOURCE_GROUP, "-n", WORKSPACE_NAME,
             "--query", "identity.principal_id", "-o", "tsv"],
            capture_output=True, text=True
        ).stdout.strip(),
        "--assignee-principal-type", "ServicePrincipal",
        "--role", "AcrPull",
        "--scope", acr_scope,
    ], capture_output=True, text=True, timeout=60)

    if result.returncode == 0:
        print("  AcrPull role assigned.")
    else:
        print(f"  Could not auto-assign role (may already exist or need Owner): {result.stderr.strip()}")
        print("  Manual command:")
        print(f"    az role assignment create --assignee <project-mi-object-id> \\")
        print(f"        --role AcrPull --scope {acr_scope}")


def deploy() -> None:
    from azure.ai.projects.models import (
        HostedAgentDefinition,
        ProtocolVersionRecord,
        AgentProtocol,
        ContainerConfiguration,
    )

    client = _get_client()
    print(f"Deploying {AGENT_NAME} -> {ACR_IMAGE}")
    print(f"Project: {PROJECT_ENDPOINT}\n")

    definition = HostedAgentDefinition(
        protocol_versions=[
            ProtocolVersionRecord(protocol=AgentProtocol.RESPONSES, version="1.0.0"),
        ],
        cpu="1",
        memory="2Gi",
        container_configuration=ContainerConfiguration(image=ACR_IMAGE),
        environment_variables=AGENT_ENV_VARS,
    )

    try:
        agent = client.agents.create_version(
            agent_name=AGENT_NAME,
            definition=definition,
            description=(
                "EnterpriseCertIQ multi-agent learning orchestrator — 8-agent pipeline "
                "(intake -> curator -> planner -> critic loop -> engagement -> assessment -> "
                "manager insights -> retrospective), grounded in Foundry IQ, Fabric IQ, and "
                "Work IQ. Synthetic data only."
            ),
        )
        version = getattr(agent, "version", "1")
        print(f"Version {version} created — polling for active status...")
    except Exception as e:
        err = str(e)
        if "already exists" in err.lower() or "conflict" in err.lower():
            print(f"Agent '{AGENT_NAME}' already exists — creating a new version...")
            agent = client.agents.create_version(
                agent_name=AGENT_NAME,
                definition=definition,
            )
            version = getattr(agent, "version", "?")
            print(f"Version {version} created — polling for active status...")
        else:
            print(f"Deploy failed: {e}")
            sys.exit(1)

    _poll_until_active(client, version)


def _poll_until_active(client, version: str, timeout_s: int = 300) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            v = client.agents.get_version(agent_name=AGENT_NAME, agent_version=str(version))
            status = v.get("status") if isinstance(v, dict) else getattr(v, "status", "unknown")
            print(f"  status: {status}")

            if status == "active":
                print(f"\n[OK] Agent '{AGENT_NAME}' version {version} is ACTIVE.")
                _print_endpoints()
                return
            elif status == "failed":
                error = v.get("error", {}) if isinstance(v, dict) else getattr(v, "error", {})
                # Print full version object for diagnosis
                print(f"\n[FAIL] Provisioning failed: {error}")
                print(f"  Full version details: {v}")
                print("\nCommon causes:")
                print("  - image_pull_failed: project MI lacks AcrPull on eciqregistry")
                print("    Fix: python scripts/deploy_hosted_agent.py --assign-acr-role")
                print("  - Container crash: check hosted/main.py startup logs")
                sys.exit(1)
        except Exception as e:
            print(f"  poll error: {e}")
        time.sleep(8)

    print(f"\n[TIMEOUT] Agent not active after {timeout_s}s — check portal for status.")
    sys.exit(1)


def _print_endpoints() -> None:
    print("\n--- Invocation endpoints ---")
    base = f"{PROJECT_ENDPOINT}/agents/{AGENT_NAME}/endpoint/protocols"
    print(f"  Responses:   POST {base}/openai/responses?api-version=v1")
    print(f"  Invocations: POST {base}/invocations?api-version=v1")
    print("\n--- Portal ---")
    print("  https://ai.azure.com/  -> Build -> Agents -> eciq-orchestrator")
    print("\nTest invocation:")
    print(f"  python scripts/deploy_hosted_agent.py --invoke \"L-1004 AZ-204\"")


def status() -> None:
    client = _get_client()
    try:
        versions = client.agents.list_versions(agent_name=AGENT_NAME)
        items = list(versions) if hasattr(versions, "__iter__") else []
        if not items:
            print(f"No versions found for agent '{AGENT_NAME}'.")
            return
        print(f"Agent: {AGENT_NAME}")
        for v in items:
            ver   = v.get("version") if isinstance(v, dict) else getattr(v, "version", "?")
            st    = v.get("status")  if isinstance(v, dict) else getattr(v, "status", "?")
            print(f"  Version {ver}: {st}")
    except Exception as e:
        print(f"Could not get status: {e}")


def invoke(prompt: str) -> None:
    client = _get_client()
    print(f"Invoking '{AGENT_NAME}' with: {prompt!r}\n")
    try:
        openai_client = client.get_openai_client(agent_name=AGENT_NAME)
        response = openai_client.responses.create(input=prompt)
        print("Response:")
        print(response.output_text)
    except Exception as e:
        print(f"Invocation failed: {e}")
        print("\nFallback — calling via REST:")
        _invoke_rest(prompt)


def _invoke_rest(prompt: str) -> None:
    import subprocess, json
    token = subprocess.run(
        ["az", "account", "get-access-token", "--resource", "https://ai.azure.com",
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True
    ).stdout.strip()
    if not token:
        print("Could not get access token. Run: az login")
        return

    import urllib.request
    url = f"{PROJECT_ENDPOINT}/agents/{AGENT_NAME}/endpoint/protocols/openai/responses?api-version=v1"
    body = json.dumps({"input": prompt, "stream": False}).encode()
    req  = urllib.request.Request(url, data=body, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            print(data.get("output_text") or json.dumps(data, indent=2))
    except Exception as e:
        print(f"REST call failed: {e}")


def delete() -> None:
    client = _get_client()
    print(f"Deleting agent '{AGENT_NAME}' and all versions...")
    try:
        client.agents.delete(agent_name=AGENT_NAME)
        print("Deleted.")
    except Exception as e:
        print(f"Delete failed: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Deploy EnterpriseCertIQ orchestrator as a Foundry Hosted Agent."
    )
    parser.add_argument("--status",          action="store_true", help="Show current agent version status.")
    parser.add_argument("--invoke",          metavar="PROMPT",    help="Send a test invocation.")
    parser.add_argument("--delete",          action="store_true", help="Delete the agent and all versions.")
    parser.add_argument("--assign-acr-role", action="store_true", help="Grant AcrPull to Foundry project MI.")
    args = parser.parse_args()

    if args.status:
        status()
    elif args.invoke:
        invoke(args.invoke)
    elif args.delete:
        delete()
    elif args.assign_acr_role:
        assign_acr_role()
    else:
        deploy()
