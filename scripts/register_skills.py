"""
Register EnterpriseCertIQ Foundry Skills via the Skills API (V1 Preview).

Requirements:
  - Service Principal with Azure AI Developer role on the project
    (AZURE_CLIENT_ID + AZURE_CLIENT_SECRET + AZURE_TENANT_ID in environment)
  - OR: run from Azure Cloud Shell (DefaultAzureCredential uses Cloud Shell token)
  - azure-identity must be installed: pip install azure-identity

Usage:
    python scripts/register_skills.py              # register all 3 skills
    python scripts/register_skills.py --list       # list skills currently in the project
    python scripts/register_skills.py --skill eciq-safety-escalation  # register one

How it works:
    1. Acquires an Entra bearer token scoped to https://ai.azure.com/.default
    2. POSTs each SKILL.md as an inline-content skill version to the Foundry Skills API
    3. Promotes each version to 'default_version' so agents can reference it by name

After running, attach skills to agents in the portal:
    Foundry portal → Agents → <agent name> → Skills → Add skill
    Or set 'skills' in register_agents_cloud_shell.py (see TODO comments below).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

SKILLS_DIR = REPO_ROOT / "skills"

# Skills to register and which agents use each one
SKILL_REGISTRY = {
    "eciq-readiness-rubric": {
        "dir": SKILLS_DIR / "eciq-readiness-rubric",
        "agents": ["eciq-readiness-critic", "eciq-assessment-agent"],
        "description": (
            "Scoring rubric for certification readiness — domain weights, mastery thresholds, "
            "pass criteria, and objection severity rules shared by readiness-critic and assessment agents."
        ),
    },
    "eciq-safety-escalation": {
        "dir": SKILLS_DIR / "eciq-safety-escalation",
        "agents": [
            "eciq-learning-path-curator", "eciq-readiness-critic", "eciq-assessment-agent",
            "eciq-plan-generator", "eciq-engagement-scheduler", "eciq-manager-insights",
            "eciq-retrospective-coach", "eciq-audio-briefing", "eciq-learner-intake",
        ],
        "description": (
            "Adversarial guard and content safety escalation policy for all EnterpriseCertIQ "
            "agents — what to block, how to respond, and what to log."
        ),
    },
    "eciq-citation-policy": {
        "dir": SKILLS_DIR / "eciq-citation-policy",
        "agents": ["eciq-learning-path-curator", "eciq-readiness-critic", "eciq-assessment-agent"],
        "description": (
            "Citation formatting and grounding requirements for all EnterpriseCertIQ agents — "
            "how to cite sources from the Knowledge Base, Fabric IQ, and MS Learn so "
            "groundedness evals pass consistently."
        ),
    },
}


def _get_token(endpoint: str) -> str:
    """Acquire Entra bearer token scoped to https://ai.azure.com/.default."""
    try:
        from azure.identity import DefaultAzureCredential
    except ImportError:
        print("[ERROR] azure-identity not installed. Run: pip install azure-identity")
        sys.exit(1)

    cred = DefaultAzureCredential()
    token = cred.get_token("https://ai.azure.com/.default")
    return token.token


def _parse_skill_md(skill_dir: Path) -> tuple[str, str]:
    """Return (description, instructions_markdown) from a SKILL.md file."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        raise FileNotFoundError(f"SKILL.md not found in {skill_dir}")

    text = skill_md.read_text(encoding="utf-8")

    # Strip YAML front matter
    fm_match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if fm_match:
        instructions = text[fm_match.end():].strip()
        # Extract description from front matter
        desc_match = re.search(r"^description:\s*(.+)$", fm_match.group(1), re.MULTILINE)
        description = desc_match.group(1).strip() if desc_match else ""
    else:
        instructions = text.strip()
        description = ""

    return description, instructions


def _api_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Foundry-Features": "Skills=V1Preview",
    }


_API_VERSION = "v1"

def _skills_url(*path_segments: str) -> str:
    """Build a Skills API URL: endpoint/skills[/segments]?api-version=v1."""
    from dotenv import load_dotenv
    import os
    load_dotenv(".env.local")
    endpoint = os.environ.get("AZURE_AI_PROJECT_ENDPOINT", "").rstrip("/")
    base = f"{endpoint}/skills"
    if path_segments:
        base = base + "/" + "/".join(path_segments)
    return f"{base}?api-version={_API_VERSION}"


def _skills_base_url(endpoint: str, project_name: str) -> str:
    """Legacy shim — kept so list_skills() still works."""
    endpoint = endpoint.rstrip("/")
    return f"{endpoint}/skills?api-version={_API_VERSION}"


def register_skill(
    skill_name: str,
    endpoint: str,
    token: str,
    dry_run: bool = False,
) -> bool:
    """Register a single skill and promote it to default_version. Returns True on success."""
    import urllib.request
    import urllib.error

    entry = SKILL_REGISTRY.get(skill_name)
    if not entry:
        print(f"[WARN] Unknown skill: {skill_name}")
        return False

    description, instructions = _parse_skill_md(entry["dir"])
    if not description:
        description = entry["description"]
    # Read the raw SKILL.md (including YAML frontmatter) — API validates the frontmatter
    raw_skill_md = (entry["dir"] / "SKILL.md").read_text(encoding="utf-8")

    auth_headers = {"Authorization": f"Bearer {token}", "Foundry-Features": "Skills=V1Preview"}

    if dry_run:
        print(f"\n[DRY RUN] Would POST to: {_skills_url(skill_name, 'versions')}")
        print(f"  description: {description[:80]}...")
        print(f"  instructions: {len(instructions)} chars")
        print(f"  agents: {', '.join(entry['agents'])}")
        return True

    # Step 1 — create skill version via multipart/form-data
    import email.mime.multipart as _mime
    import uuid
    version_url = _skills_url(skill_name, "versions")
    print(f"\nRegistering skill '{skill_name}'...")
    print(f"  POST {version_url}")

    boundary = uuid.uuid4().hex
    body_parts = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="SKILL.md"\r\n'
        f"Content-Type: text/markdown\r\n\r\n"
        f"{raw_skill_md}\r\n"
        f"--{boundary}--\r\n"
    )
    multipart_data = body_parts.encode("utf-8")
    multipart_headers = {
        **auth_headers,
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }

    req = urllib.request.Request(version_url, data=multipart_data, headers=multipart_headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read())
            version_id = body.get("version_id") or body.get("id") or body.get("name") or "1"
            print(f"  [OK] Version created: {version_id}")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        print(f"  [ERROR] {e.code}: {err_body[:400]}")
        return False

    # Note: the Skills API (v1 preview) does not expose a programmatic promote endpoint.
    # For a fresh install, v1 is automatically the default_version.
    # To promote a later version, use the portal: Build -> Skills -> <skill> -> Set as default.

    print(f"  Attach to agents: {', '.join(entry['agents'])}")
    return True


def list_skills(endpoint: str, token: str):
    import urllib.request
    import urllib.error

    base_url = _skills_base_url(endpoint, "")
    print(f"\nGET {base_url}")
    req = urllib.request.Request(base_url, headers=_api_headers(token), method="GET")
    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read())
            skills = body.get("data") or body.get("value") or body.get("skills") or (body if isinstance(body, list) else [])
            if not skills:
                print("  (no skills found)")
            for s in skills:
                name = s.get("name") or s.get("skill_name", "?")
                ver = s.get("default_version") or s.get("version_id", "")
                print(f"  {name}  (default: {ver})")
    except urllib.error.HTTPError as e:
        print(f"  [ERROR] {e.code}: {e.read().decode()[:300]}")


def main():
    parser = argparse.ArgumentParser(description="Register EnterpriseCertIQ Foundry Skills")
    parser.add_argument("--skill", help="Register a single skill by name (default: all)")
    parser.add_argument("--list", action="store_true", help="List registered skills")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be sent, don't call API")
    args = parser.parse_args()

    endpoint = os.environ.get("AZURE_AI_PROJECT_ENDPOINT", "")
    if not endpoint:
        # Fall back to settings
        try:
            from config.settings import get_settings
            endpoint = get_settings().azure_ai_project_endpoint
        except Exception:
            pass

    if not endpoint:
        print("[ERROR] AZURE_AI_PROJECT_ENDPOINT not set. Export it or add to .env.local")
        sys.exit(1)

    print(f"Project endpoint: {endpoint}")

    if args.dry_run:
        token = "dry-run-token"
    else:
        print("Acquiring Entra token (DefaultAzureCredential)...")
        token = _get_token(endpoint)
        print("  [OK] Token acquired")

    if args.list:
        list_skills(endpoint, token)
        return

    skill_names = [args.skill] if args.skill else list(SKILL_REGISTRY.keys())
    results = {}
    for name in skill_names:
        ok = register_skill(name, endpoint, token, dry_run=args.dry_run)
        results[name] = "OK" if ok else "FAILED"

    print("\n=== Summary ===")
    for name, status in results.items():
        agents = SKILL_REGISTRY.get(name, {}).get("agents", [])
        print(f"  {status}  {name}  -> attach to: {', '.join(agents)}")

    if not args.dry_run:
        print("\nNext: Foundry portal → Agents → <agent name> → Skills → Add skill")
        print("Or re-run register_agents_cloud_shell.py with --recreate after adding 'skills' to each agent definition.")


if __name__ == "__main__":
    main()
