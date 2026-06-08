"""
Index/refresh the Foundry IQ knowledge base in Azure AI Search.

Reads local cert data + markdown docs and upserts them into the index. Because it
upserts by stable key (`cert-{id}`, `{doc}-s{n}`), re-running after adding new certs
just refreshes the index — safe and idempotent.

Run after any change to cert_structures.json or backend/data/documents/:
    python scripts/upload_to_search.py

Config comes from the environment / .env (NO secrets in source):
    FOUNDRY_IQ_ENDPOINT      = https://<your-search>.search.windows.net
    FOUNDRY_IQ_INDEX_NAME    = cert-knowledge-base
    AZURE_SEARCH_KEY         = <search admin key>
"""
import json
import re
import sys
from pathlib import Path

# Ensure the repo root is importable when run as `python scripts/upload_to_search.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SimpleField, SearchableField, SearchFieldDataType,
)

from config.settings import get_settings


def ensure_index(endpoint: str, index: str, key: str) -> None:
    """Create the index if it doesn't exist (idempotent) so seeding works on a
    fresh search service."""
    ic = SearchIndexClient(endpoint, AzureKeyCredential(key))
    existing = {i.name for i in ic.list_indexes()}
    if index in existing:
        print(f"Index '{index}' already exists.")
        return
    ic.create_index(SearchIndex(name=index, fields=[
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="title", type=SearchFieldDataType.String),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SimpleField(name="source_url", type=SearchFieldDataType.String),
    ]))
    print(f"Created index '{index}'.")

CERT_LEARN_URLS = {
    "AZ-204": "https://learn.microsoft.com/credentials/certifications/azure-developer/",
    "AZ-400": "https://learn.microsoft.com/credentials/certifications/devops-engineer/",
    "DP-203": "https://learn.microsoft.com/credentials/certifications/azure-data-engineer/",
    "AZ-305": "https://learn.microsoft.com/credentials/certifications/azure-solutions-architect/",
    "AI-102": "https://learn.microsoft.com/credentials/certifications/azure-ai-engineer/",
    "DP-100": "https://learn.microsoft.com/credentials/certifications/azure-data-scientist/",
    "AI-900": "https://learn.microsoft.com/credentials/certifications/azure-ai-fundamentals/",
    "SC-100": "https://learn.microsoft.com/credentials/certifications/cybersecurity-architect-expert/",
    "MS-102": "https://learn.microsoft.com/credentials/certifications/microsoft-365-administrator-expert/",
    "AZ-104": "https://learn.microsoft.com/credentials/certifications/azure-administrator/",
    "AZ-700": "https://learn.microsoft.com/credentials/certifications/azure-network-engineer/",
    "DP-900": "https://learn.microsoft.com/credentials/certifications/azure-data-fundamentals/",
}


def main() -> int:
    s = get_settings()
    endpoint = s.foundry_iq_endpoint
    index = s.foundry_iq_index_name
    key = s.azure_search_key

    if not endpoint or endpoint == "local" or not key:
        print("ERROR: set FOUNDRY_IQ_ENDPOINT (https://...search.windows.net) and "
              "AZURE_SEARCH_KEY in your environment / .env before running.")
        return 1

    ensure_index(endpoint, index, key)
    client = SearchClient(endpoint, index, AzureKeyCredential(key))
    repo_root = Path(__file__).resolve().parent.parent
    docs = []

    # ── 1. cert_structures.json — one doc per cert (now all 9) ──────────────
    certs = json.loads((repo_root / "backend/data/synthetic/cert_structures.json").read_text())
    for cert_id, c in certs.items():
        domains_text = " | ".join(
            f"{d['name']} ({d['weight_pct']}%) — {', '.join(d['services'])}"
            for d in c["domains"]
        )
        docs.append({
            "id": f"cert-{cert_id}",
            "title": f"{cert_id}: {c['cert_name']}",
            "content": (
                f"Role: {c['role']}. Passing score: {c['passing_score']}. "
                f"Recommended study hours: {c['recommended_study_hours']}. "
                f"Domains: {domains_text}."
            ),
            "source_url": CERT_LEARN_URLS.get(cert_id, ""),
        })
        print(f"  queued cert doc: {cert_id}")

    # ── 2. Markdown docs — one doc per ## section ────────────────────────────
    for md_path in (repo_root / "backend/data/documents").glob("*.md"):
        text = md_path.read_text(encoding="utf-8")
        raw_sections = re.split(r"\n(## .+)", text)
        preamble = raw_sections[0].strip()
        if preamble:
            docs.append({"id": f"{md_path.stem}-s0",
                         "title": md_path.stem.replace("_", " ").title(),
                         "content": preamble[:4000], "source_url": ""})
        for i, (heading, body) in enumerate(zip(raw_sections[1::2], raw_sections[2::2]), start=1):
            body = body.strip()
            if not body:
                continue
            docs.append({"id": f"{md_path.stem}-s{i}",
                         "title": heading.lstrip("# ").strip(),
                         "content": body[:4000], "source_url": ""})

    print(f"\nUpserting {len(docs)} documents to '{index}'...")
    results = client.upload_documents(documents=docs)
    failures = [r for r in results if not r.succeeded]
    print(f"Done. Succeeded: {len(docs) - len(failures)}  |  Failed: {len(failures)}")
    for f in failures:
        print(f"  FAILED key={f.key}  error={f.error_message}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
