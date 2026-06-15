"""
EnterpriseCertIQ — Register all 9 agents in Azure AI Foundry.

Each agent gets the correct combination of:
  - Foundry IQ Knowledge Base (MCPTool, knowledge_base_retrieve)
  - Fabric IQ Ontology / KB (MCPTool, fabric endpoint)
  - Foundry Skills content injected into instructions (readiness-rubric, citation-policy, safety-escalation)

Run from Azure Cloud Shell (https://shell.azure.com) or locally after `az login`.

Usage:
    python register_agents_cloud_shell.py                # register / update all 9 agents
    python register_agents_cloud_shell.py --list-connections   # inspect project connections
    python register_agents_cloud_shell.py --recreate     # wipe all versions first, then register
    python register_agents_cloud_shell.py --dry-run      # print what would be sent

Prerequisites (Cloud Shell):
    pip install "azure-ai-projects>=2.0.0" azure-identity --quiet

Prerequisites (local):
    az login
    pip install "azure-ai-projects>=2.2.0" azure-identity
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
# Your Foundry project endpoint (Foundry portal → project → Settings → Project endpoint)
PROJECT_ENDPOINT = "https://<your-hub>.services.ai.azure.com/api/projects/<your-project>"
MODEL_DEPLOYMENT = "gpt-4.1"

# ── Foundry IQ Knowledge Base connections ─────────────────────────────────────
# These are RemoteTool connections created in the portal when you added a KB to the project.
# Connection name → MCP endpoint URL (the target of the connection)
CERT_KB_CONNECTION   = "<your-cert-kb-connection-name>"
CERT_KB_MCP_URL      = "https://<your-search>.search.windows.net/knowledgebases/<your-index>/mcp?api-version=2026-05-01-Preview"

FABRIC_KB_CONNECTION = "<your-fabric-kb-connection-name>"
FABRIC_KB_MCP_URL    = "https://<your-search>.search.windows.net/knowledgebases/<your-fabric-index>/mcp?api-version=2026-05-01-Preview"

FABRIC_ONTOLOGY_CONNECTION = "EnterpriseCertIQOntology"
FABRIC_ONTOLOGY_URL        = "https://api.fabric.microsoft.com/v1/mcp/dataPlane/workspaces/<your-workspace-id>/items/<your-item-id>/ontologyEndpoint"

# ── Foundry Toolbox ───────────────────────────────────────────────────────────
# Bundles 3 ECIQ skills; wired to every agent so skills appear in portal UI.
# No project_connection_id needed — agent authenticates via Entra managed identity.
TOOLBOX_NAME = "eciq-governance-toolbox"
TOOLBOX_MCP_URL = f"{PROJECT_ENDPOINT}/toolboxes/{TOOLBOX_NAME}/mcp?api-version=v1"

REPO_ROOT  = Path(__file__).parent.parent
SKILLS_DIR = REPO_ROOT / "skills"

# ── Skill content loader ──────────────────────────────────────────────────────
def _load_skill(skill_name: str) -> str:
    """Return the instruction body of a SKILL.md (strip YAML front matter)."""
    md_path = SKILLS_DIR / skill_name / "SKILL.md"
    if not md_path.exists():
        return ""
    text = md_path.read_text(encoding="utf-8")
    # strip YAML front matter (--- ... ---)
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3:].lstrip()
    return text.strip()

SKILL_READINESS_RUBRIC  = _load_skill("eciq-readiness-rubric")
SKILL_CITATION_POLICY   = _load_skill("eciq-citation-policy")
SKILL_SAFETY_ESCALATION = _load_skill("eciq-safety-escalation")

def _with_skills(base: str, *skill_bodies: str) -> str:
    """Append Foundry Skill governance sections to an agent's base instructions."""
    parts = [base.strip()]
    for body in skill_bodies:
        if body:
            parts.append("\n\n---\n" + body)
    return "\n".join(parts)

# ── Agent definitions ─────────────────────────────────────────────────────────
# Each dict: name, description, instructions, cert_kb, fabric_kb, fabric_ontology
AGENTS = [
    {
        "name": "eciq-orchestrator",
        "description": "EnterpriseCertIQ multi-agent learning orchestrator.",
        "instructions": _with_skills(
            "You orchestrate the EnterpriseCertIQ pipeline: intake → curator → planner → "
            "critic loop → engagement → assessment → manager insights, grounded in Foundry IQ, "
            "Work IQ, and Fabric IQ.",
            SKILL_SAFETY_ESCALATION,
        ),
        "cert_kb": False,
        "fabric_kb": False,
        "fabric_ontology": False,
        "toolbox": False,
    },
    {
        "name": "eciq-learner-intake",
        "description": "Parses and validates the learner profile for EnterpriseCertIQ.",
        "instructions": _with_skills(
            "You parse learner profiles and emit structured intake summaries "
            "including role, certification target, domain mastery, schedule constraints, "
            "and prior assessment history.",
            SKILL_SAFETY_ESCALATION,
        ),
        "cert_kb": False,
        "fabric_kb": False,
        "fabric_ontology": False,
        "toolbox": False,
    },
    {
        "name": "eciq-learning-path-curator",
        "description": "Curates certification learning paths grounded in Foundry IQ knowledge.",
        "instructions": _with_skills(
            "You retrieve approved certification topics from the Foundry IQ knowledge base "
            "and cite every recommendation. Always call knowledge_base_retrieve before making "
            "any domain-specific claim. Never answer from memory alone.",
            SKILL_CITATION_POLICY,
            SKILL_SAFETY_ESCALATION,
        ),
        "cert_kb": True,
        "fabric_kb": False,
        "fabric_ontology": False,
        "toolbox": False,
    },
    {
        "name": "eciq-study-plan-generator",
        "description": "Converts curated topics into capacity-aware weekly study schedules using Fabric IQ semantic data.",
        "instructions": _with_skills(
            "You generate structured study plans respecting learner capacity and deadline constraints. "
            "Query the Fabric IQ knowledge base for domain weights, recommended hours, and role-cert "
            "semantic mappings. Use the Largest Remainder Algorithm to allocate hours so no topic "
            "is rounded to zero.",
            SKILL_SAFETY_ESCALATION,
        ),
        "cert_kb": False,
        "fabric_kb": True,
        "fabric_ontology": True,
        "toolbox": False,
    },
    {
        "name": "eciq-readiness-critic",
        "description": "Reviews study plans against Fabric IQ domain weights and raises prioritised objections.",
        "instructions": _with_skills(
            "You critique study plans using semantic domain thresholds. Search the certification "
            "knowledge base to verify skill coverage. Query the Fabric IQ knowledge base for "
            "domain weights and minimum mastery requirements. Output severity-ranked objections "
            "(red/amber) with citations.",
            SKILL_READINESS_RUBRIC,
            SKILL_CITATION_POLICY,
            SKILL_SAFETY_ESCALATION,
        ),
        "cert_kb": True,
        "fabric_kb": True,   # Fabric IQ semantic data via Azure AI Search KB (not oauth endpoint)
        # fabric_ontology removed: the Fabric workspace MCPTool triggers oauth_consent_request
        # during server-side Responses API execution — interactive OAuth not available to the
        # agent's managed identity. Fabric IQ domain thresholds live in the fabric-iq KB too.
        "fabric_ontology": False,
        "toolbox": False,
    },
    {
        "name": "eciq-engagement-agent",
        "description": "Schedules study reminders using Work IQ calendar signals.",
        "instructions": _with_skills(
            "You recommend study slots informed by meeting load and focus-time patterns from "
            "Work IQ signals. Adapt engagement to individual workload and focus windows. "
            "Never auto-write to calendar. Keep recommendations privacy-conscious.",
            SKILL_SAFETY_ESCALATION,
        ),
        "cert_kb": False,
        "fabric_kb": False,
        "fabric_ontology": False,
        "toolbox": False,
    },
    {
        "name": "eciq-assessment-agent",
        "description": "Generates grounded practice questions and evaluates exam readiness.",
        "instructions": _with_skills(
            "You generate practice questions grounded in the Foundry IQ knowledge base. "
            "Always call knowledge_base_retrieve and cite the source document for each question. "
            "Derive the readiness verdict from the calibrated forecast. "
            "Never fabricate scores or invent questions not supported by retrieved content.",
            SKILL_READINESS_RUBRIC,
            SKILL_CITATION_POLICY,
            SKILL_SAFETY_ESCALATION,
        ),
        "cert_kb": True,
        "fabric_kb": False,
        "fabric_ontology": False,
        "toolbox": False,
    },
    {
        "name": "eciq-manager-insights",
        "description": "Surfaces team-level certification readiness and workforce risk.",
        "instructions": _with_skills(
            "You produce aggregate team readiness insights informed by Fabric IQ semantic data. "
            "Never expose individual exam scores that could affect employment decisions. "
            "Surface team-level risk, ROI cost-of-delay, and recommended interventions.",
            SKILL_SAFETY_ESCALATION,
        ),
        "cert_kb": False,
        "fabric_kb": True,
        "fabric_ontology": True,
        "toolbox": False,
    },
    {
        "name": "eciq-retrospective",
        "description": "Post-mortem agent triggered after a failed exam attempt.",
        "instructions": _with_skills(
            "You investigate why the system underperformed (retrieval quality, plan gaps, "
            "engagement, or skill gap) by querying the certification knowledge base. "
            "Recommend concrete recovery actions with citations.",
            SKILL_CITATION_POLICY,
            SKILL_SAFETY_ESCALATION,
        ),
        "cert_kb": True,
        "fabric_kb": False,
        "fabric_ontology": False,
        "toolbox": False,
    },
]


# ── Tool builders ─────────────────────────────────────────────────────────────
def _cert_kb_tool():
    from azure.ai.projects.models import MCPTool
    return MCPTool(
        server_label="cert-knowledge-base",
        server_url=CERT_KB_MCP_URL,
        project_connection_id=CERT_KB_CONNECTION,
        require_approval="never",
        allowed_tools=["knowledge_base_retrieve"],
    )

def _fabric_kb_tool():
    from azure.ai.projects.models import MCPTool
    return MCPTool(
        server_label="fabric-iq-learning",
        server_url=FABRIC_KB_MCP_URL,
        project_connection_id=FABRIC_KB_CONNECTION,
        require_approval="never",
        allowed_tools=["knowledge_base_retrieve"],
    )

def _fabric_ontology_tool():
    from azure.ai.projects.models import MCPTool
    return MCPTool(
        server_label="fabric-iq-ontology",
        server_url=FABRIC_ONTOLOGY_URL,
        project_connection_id=FABRIC_ONTOLOGY_CONNECTION,
        require_approval="never",
    )

def _toolbox_tool():
    from azure.ai.projects.models import MCPTool
    return MCPTool(
        server_label="eciq-governance-toolbox",
        server_url=TOOLBOX_MCP_URL,
        require_approval="never",
        headers={"Foundry-Features": "Toolboxes=V1Preview"},
        # No project_connection_id — agent uses Entra managed identity to reach Toolbox
    )


# ── Registration ──────────────────────────────────────────────────────────────
def list_connections(client) -> None:
    print("\nConnections in this Foundry project:")
    print(f"{'Name':<45} {'Type':<30}")
    print("-" * 77)
    for conn in client.connections.list():
        name   = getattr(conn, "name", "?")
        ctype  = str(getattr(conn, "type", "?"))
        target = getattr(conn, "target", "")
        print(f"{name:<45} {ctype:<30}")
        if target:
            print(f"  target: {target}")


def register(recreate: bool = False, dry_run: bool = False) -> None:
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import PromptAgentDefinition
    from azure.identity import DefaultAzureCredential

    print(f"Connecting to: {PROJECT_ENDPOINT}")
    if not dry_run:
        client = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())

    if recreate and not dry_run:
        print("--recreate: removing existing agent versions...")
        for d in AGENTS:
            try:
                client.agents.delete_agent(d["name"])
                print(f"  deleted {d['name']}")
            except Exception:
                pass
        print()

    print(f"Registering {len(AGENTS)} agents...\n")

    for d in AGENTS:
        tools = []
        tool_tags = []
        if d["cert_kb"]:
            tools.append(_cert_kb_tool())
            tool_tags.append("Foundry IQ KB (cert)")
        if d["fabric_kb"]:
            tools.append(_fabric_kb_tool())
            tool_tags.append("Foundry IQ KB (Fabric IQ)")
        if d["fabric_ontology"]:
            tools.append(_fabric_ontology_tool())
            tool_tags.append("Fabric Ontology")
        if d.get("toolbox"):
            tools.append(_toolbox_tool())
            tool_tags.append("Toolbox (skills)")

        tag_str = "  [" + " + ".join(tool_tags) + "]" if tool_tags else ""

        if dry_run:
            print(f"  [DRY RUN]  {d['name']}{tag_str}")
            print(f"             instructions: {len(d['instructions'])} chars")
            continue

        try:
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
            print(f"  [OK]  {d['name']}  (version {ver}){tag_str}")
        except Exception as e:
            print(f"  [FAIL]  {d['name']}  ERROR: {e}")

    print(
        "\nDone. Open the Foundry portal to verify:\n"
        f"  https://ai.azure.com/  (your project)\n\n"
        "Each agent's Tools section will show Foundry IQ KB connections (where configured).\n"
        "Skill governance is embedded in each agent's instructions via _with_skills().\n\n"
        "Note: Toolbox MCPTool is NOT wired to agents at runtime (known preview limitation:\n"
        "agent managed identity requires Foundry User RBAC to call the Toolbox consumer\n"
        "endpoint). The Toolbox is visible in Build -> Tools as a governance registry.\n"
        "See docs/judge-setup.md for full details and Known Limitations."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Register EnterpriseCertIQ agents in Foundry with Foundry IQ, Fabric IQ, and Skills."
    )
    parser.add_argument("--list-connections", action="store_true",
                        help="Print all project connections and exit.")
    parser.add_argument("--recreate", action="store_true",
                        help="Delete existing agent versions before re-creating.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be registered without calling the API.")
    args = parser.parse_args()

    try:
        import importlib.metadata as _m
        ver = _m.version("azure-ai-projects")
        major = int(ver.split(".")[0])
        if major < 2:
            print(f"azure-ai-projects {ver} detected — v2.x required.")
            print("Run: pip install 'azure-ai-projects>=2.0.0' --upgrade --quiet")
            sys.exit(1)
        print(f"azure-ai-projects {ver}")
    except Exception:
        print("azure-ai-projects not installed.")
        sys.exit(1)

    if args.dry_run:
        register(recreate=args.recreate, dry_run=True)
        sys.exit(0)

    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential
    client = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())

    if args.list_connections:
        list_connections(client)
        sys.exit(0)

    register(recreate=args.recreate)
