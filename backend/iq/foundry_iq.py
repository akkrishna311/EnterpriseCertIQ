"""
Foundry IQ integration — grounded knowledge retrieval.

Local mode:  simple TF-IDF style keyword search over ./data/documents/
Azure mode:  calls Azure AI Search index (Foundry IQ knowledge base)

Returns citations with span-anchored excerpts.
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Optional

from config.settings import get_settings

logger = logging.getLogger(__name__)

AI_DISCLOSURE = "Retrieved from approved knowledge base via Foundry IQ"


class SearchResult:
    def __init__(self, doc_id: str, title: str, excerpt: str, score: float, source_url: str = ""):
        self.doc_id = doc_id
        self.title = title
        self.excerpt = excerpt
        self.score = score
        self.source_url = source_url
        self.span_id = str(uuid.uuid4())[:8]

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "excerpt": self.excerpt,
            "score": round(self.score, 3),
            "span_id": self.span_id,
            "source_url": self.source_url,
            "ai_disclosure": AI_DISCLOSURE,
        }


class FoundryIQClient:
    def __init__(self):
        self.s = get_settings()
        self._docs: dict[str, str] = {}
        self._loaded = False

    def _load_local_docs(self) -> None:
        if self._loaded:
            return
        docs_dir = Path(self.s.data_dir) / "documents"
        for path in docs_dir.glob("*.md"):
            self._docs[path.stem] = path.read_text(encoding="utf-8")
        # Also load cert_structures.json as a searchable doc
        cert_path = Path(self.s.data_dir) / "synthetic" / "cert_structures.json"
        if cert_path.exists():
            self._docs["cert_structures"] = cert_path.read_text(encoding="utf-8")
        self._loaded = True
        logger.info("Foundry IQ (local): loaded %d documents", len(self._docs))

    def _score_doc(self, doc_text: str, query: str) -> float:
        query_terms = set(re.sub(r"[^\w\s]", "", query.lower()).split())
        doc_lower = doc_text.lower()
        hits = sum(1 for term in query_terms if term in doc_lower)
        return hits / max(len(query_terms), 1)

    def _extract_excerpt(self, doc_text: str, query: str, max_chars: int = 400) -> str:
        query_terms = set(re.sub(r"[^\w\s]", "", query.lower()).split())
        lines = doc_text.split("\n")
        best_line = ""
        best_hits = 0
        for line in lines:
            hits = sum(1 for term in query_terms if term in line.lower())
            if hits > best_hits:
                best_hits = hits
                best_line = line
        return best_line.strip()[:max_chars] if best_line else doc_text[:max_chars]

    async def search(self, query: str, top_k: int = 3) -> list[SearchResult]:
        if self.s.foundry_iq_endpoint == "local":
            return await self._search_local(query, top_k)
        return await self._search_azure(query, top_k)

    async def _search_local(self, query: str, top_k: int) -> list[SearchResult]:
        self._load_local_docs()
        scored = []
        for doc_id, text in self._docs.items():
            score = self._score_doc(text, query)
            if score > 0:
                excerpt = self._extract_excerpt(text, query)
                scored.append(SearchResult(
                    doc_id=doc_id,
                    title=doc_id.replace("_", " ").title(),
                    excerpt=excerpt,
                    score=score,
                ))
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:top_k]

    async def _search_azure(self, query: str, top_k: int) -> list[SearchResult]:
        # Foundry IQ retrieval via Azure AI Projects SDK
        # Fill in when FOUNDRY_IQ_ENDPOINT is configured to your project endpoint
        import httpx
        endpoint = self.s.foundry_iq_endpoint
        index = self.s.foundry_iq_index_name
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(
                    f"{endpoint}/indexes/{index}/docs/search",
                    params={"api-version": "2023-11-01"},  # required by Azure AI Search REST
                    json={"search": query, "top": top_k, "select": "id,title,content,source_url"},
                    headers={"api-key": self.s.azure_search_key or self.s.azure_ai_api_key},
                )
                r.raise_for_status()
                hits = r.json().get("value", [])
                return [
                    SearchResult(
                        doc_id=h.get("id", ""),
                        title=h.get("title", ""),
                        excerpt=h.get("content", "")[:400],
                        score=h.get("@search.score", 0.0),
                        source_url=h.get("source_url", ""),
                    )
                    for h in hits
                ]
        except Exception as e:
            logger.error("Foundry IQ Azure search failed, falling back to local: %s", e)
            return await self._search_local(query, top_k)


_client: Optional[FoundryIQClient] = None


def get_foundry_iq() -> FoundryIQClient:
    global _client
    if _client is None:
        _client = FoundryIQClient()
    return _client
