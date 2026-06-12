"""
EnterpriseCertIQ — Register all 9 agents in Azure AI Foundry with native Foundry IQ grounding.

Run from Azure Cloud Shell (https://shell.azure.com). No 'az login' needed —
DefaultAzureCredential picks up the portal session automatically.

Usage (Cloud Shell bash):
    pip install "azure-ai-projects>=2.0.0" azure-identity --quiet
    python register_agents_cloud_shell.py

    # List your Foundry connections first to find the search connection name:
    python register_agents_cloud_shell.py --list-connections

    # Recreate agents (wipes existing versions):
    python register_agents_cloud_shell.py --recreate
"""
from __future__ import annotations

import argparse
import sys

# ── Config ────────────────────────────────────────────────────────────────────
PROJECT_ENDPOINT = "https://agenticaifoundrypoc.services.ai.azure.com/api/projects/aipoc"
MODEL_DEPLOYMENT = "gpt-4.1"
INDEX_NAME       = "cert-knowledge-base"

# Foundry portal → Settings → Connections → find your Azure AI Search connection → copy its Name.
# Run with --list-connections first if you are unsure.
SEARCH_CONNECTION_NAME = "REPLACE_WITH_YOUR_SEARCH_CONNECTION_NAME"
# ─────────────────────────────────────────────────────────────────────────────

# Agents that get Foundry IQ (search index) attached — the ones that need grounded retrieval.
GROUNDED_AGENTS = {
    "eciq-learning-path-curator",
    "eciq-assessment-agent",
    "eciq-readiness-critic",
}

AGENTS = [
    {
        "name": "eciq-orchestrator",
        "description": "EnterpriseCertIQ multi-agent learning orchestrator.",
        "instructions": (
            "You orchestrate the EnterpriseCertIQ pipeline: intake → curator → planner → "
            "critic loop → engagement → assessment → manager insights, grounded in Foundry IQ, "
            "Work IQ, and Fabric IQ."
        ),
    },
    {
        "name": "eciq-learner-intake",
        "description": "Parses and validates the learner profile for EnterpriseCertIQ.",
        "instructions": "You parse learner profiles and emit structured intake summaries.",
    },
    {
        "name": "eciq-learning-path-curator",
        "description": "Curates certification learning paths grounded in Foundry IQ knowledge.",
        "instructions": (
            "You retrieve approved certification topics from the Foundry IQ knowledge base "
            "and cite every recommendation. Always use the azure_ai_search tool to ground "
            "your answers — never answer from memory alone."
        ),
    },
    {
        "name": "eciq-study-plan-generator",
        "description": "Converts curated topics into capacity-aware weekly study schedules.",
        "instructions": (
            "You generate structured study plans respecting learner capacity and deadline "
            "constraints."
        ),
    },
    {
        "name": "eciq-readiness-critic",
        "description": "Reviews study plans against Fabric IQ domain weights and raises prioritised objections.",
        "instructions": (
            "You critique study plans using semantic domain thresholds. Search the knowledge "
            "base to verify skill coverage and output severity-ranked objections with citations."
        ),
    },
    {
        "name": "eciq-engagement-agent",
        "description": "Schedules study reminders using Work IQ calendar signals.",
        "instructions": (
            "You recommend study slots informed by meeting load and focus-time patterns. "
            "Never auto-write to calendar."
        ),
    },
    {
        "name": "eciq-assessment-agent",
        "description": "Generates grounded practice questions and evaluates exam readiness.",
        "instructions": (
            "You generate practice questions grounded in the Foundry IQ knowledge base. "
            "Always use the azure_ai_search tool and cite the source document for each question. "
            "Derive the readiness verdict from the calibrated forecast."
        ),
    },
    {
        "name": "eciq-manager-insights",
        "description": "Surfaces team-level certification readiness and workforce risk.",
        "instructions": (
            "You produce aggregate team readiness insights. Never expose individual exam scores "
            "that could affect employment decisions."
        ),
    },
    {
        "name": "eciq-retrospective",
        "description": "Post-mortem agent triggered after a failed exam attempt.",
        "instructions": (
            "You investigate why the system underperformed (retrieval, plan, engagement, or "
            "skill gap) and recommend recovery actions."
        ),
    },
]


def list_connections(client) -> None:
    print("\nConnections in this Foundry project:")
    print(f"{'Name':<40} {'Type':<30}")
    print("-" * 72)
    for conn in client.connections.list():
        print(f"{conn.name:<40} {getattr(conn, 'connection_type', '?'):<30}")
    print("\nSet SEARCH_CONNECTION_NAME at the top of this script to the Name of your AI Search connection.")


def _build_search_tool(client):
    """Resolve the connection ID and return an AzureAISearchTool.

    VECTOR_SEMANTIC_HYBRID = vector similarity + BM25 keyword + semantic reranking.
    This is the "Agentic Retrieval" mode — an LLM decomposes complex questions into
    parallel subqueries and reranks results, yielding ~36% higher response quality
    than a plain keyword search.  Requires a semantic configuration on the index
    (set one up in Azure AI Search portal → your index → Semantic configurations).
    """
    from azure.ai.projects.models import (
        AzureAISearchTool,
        AzureAISearchToolResource,
        AISearchIndexResource,
        AzureAISearchQueryType,
    )
    conn = client.connections.get(SEARCH_CONNECTION_NAME)
    return AzureAISearchTool(
        azure_ai_search=AzureAISearchToolResource(
            indexes=[
                AISearchIndexResource(
                    project_connection_id=conn.id,
                    index_name=INDEX_NAME,
                    query_type=AzureAISearchQueryType.VECTOR_SEMANTIC_HYBRID,
                )
            ]
        )
    )


def register(recreate: bool = False) -> None:
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    print(f"Connecting to: {PROJECT_ENDPOINT}")
    client = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())

    if SEARCH_CONNECTION_NAME == "REPLACE_WITH_YOUR_SEARCH_CONNECTION_NAME":
        print("\n⚠  SEARCH_CONNECTION_NAME is not set.")
        print("   Run with --list-connections to find the right name, then edit this script.\n")
        print("   Registering agents WITHOUT Foundry IQ grounding (instructions only)...\n")
        search_tool = None
    else:
        print(f"Resolving search connection: {SEARCH_CONNECTION_NAME!r}")
        try:
            search_tool = _build_search_tool(client)
            print(f"  ✓  Search tool ready — index: {INDEX_NAME}\n")
        except Exception as e:
            print(f"  ✗  Could not resolve connection ({e}) — registering without search tool.\n")
            search_tool = None

    # Delete existing agents first if --recreate
    if recreate:
        print("--recreate: removing existing agent versions...")
        try:
            for d in AGENTS:
                try:
                    client.agents.delete_agent(d["name"])
                    print(f"  deleted {d['name']}")
                except Exception:
                    pass
        except Exception:
            pass
        print()

    print(f"Registering {len(AGENTS)} agents with Foundry IQ grounding on: "
          f"{', '.join(GROUNDED_AGENTS) if search_tool else 'none (no connection set)'})\n")

    for d in AGENTS:
        attach_search = search_tool is not None and d["name"] in GROUNDED_AGENTS
        tools = [search_tool] if attach_search else []
        try:
            from azure.ai.projects.models import PromptAgentDefinition
            definition = PromptAgentDefinition(
                kind="prompt",
                model=MODEL_DEPLOYMENT,
                instructions=d["instructions"],
                tools=tools,
            )
            v = client.agents.create_version(
                agent_name=d["name"],
                definition=definition,
                description=d["description"],
            )
            ver = getattr(v, "version", "?")
            iq_tag = "  [+ Foundry IQ]" if attach_search else ""
            print(f"  ✓  {d['name']}  (version {ver}){iq_tag}")
        except Exception as e:
            print(f"  ✗  {d['name']}  ERROR: {e}")

    print(
        "\nDone. Open the Foundry portal → your project → Agents to verify.\n"
        "Agents with [+ Foundry IQ] will show the search index under 'Knowledge bases'.\n"
        f"Portal: https://ai.azure.com/  (project 'aipoc')"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Register EnterpriseCertIQ agents in Foundry with Foundry IQ.")
    parser.add_argument("--list-connections", action="store_true",
                        help="Print all connections in the project and exit.")
    parser.add_argument("--recreate", action="store_true",
                        help="Delete existing agent versions before re-creating.")
    args = parser.parse_args()

    try:
        import importlib.metadata as _m
        ver = _m.version("azure-ai-projects")
        major = int(ver.split(".")[0])
        if major < 2:
            print(f"⚠  azure-ai-projects {ver} detected — v2.x required for AzureAISearchTool.")
            print("   Run: pip install 'azure-ai-projects>=2.0.0' --upgrade --quiet")
            sys.exit(1)
    except Exception:
        print("azure-ai-projects not installed. Run:\n  pip install 'azure-ai-projects>=2.0.0' azure-identity --quiet")
        sys.exit(1)

    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential
    client = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())

    if args.list_connections:
        list_connections(client)
        sys.exit(0)

    register(recreate=args.recreate)
