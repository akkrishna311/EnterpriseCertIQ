"""
Storage abstraction — local JSON files (dev) or Azure Cosmos DB (cloud).
Cosmos is stubbed — fill in connection string to activate.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config.settings import StorageBackend, get_settings

logger = logging.getLogger(__name__)


class LocalJSONStore:
    """Append-write JSON store backed by flat files, one file per container."""

    def __init__(self, store_dir: str):
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, container: str) -> Path:
        return self.store_dir / f"{container}.json"

    def _read(self, container: str) -> list[dict]:
        p = self._path(container)
        if not p.exists():
            return []
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _write(self, container: str, records: list[dict]) -> None:
        self._path(container).write_text(
            json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    async def upsert(self, container: str, item: dict) -> dict:
        records = self._read(container)
        item_id = item.get("id") or item.get("run_id") or str(uuid.uuid4())
        item["id"] = item_id
        item["_updated_at"] = datetime.now(timezone.utc).isoformat()
        existing_idx = next((i for i, r in enumerate(records) if r.get("id") == item_id), None)
        if existing_idx is not None:
            records[existing_idx] = item
        else:
            records.append(item)
        self._write(container, records)
        return item

    async def get(self, container: str, item_id: str) -> Optional[dict]:
        records = self._read(container)
        return next((r for r in records if r.get("id") == item_id), None)

    async def query(self, container: str, partition_key: str, partition_value: str) -> list[dict]:
        records = self._read(container)
        return [r for r in records if r.get(partition_key) == partition_value]

    async def list_all(self, container: str) -> list[dict]:
        return self._read(container)

    async def delete(self, container: str, item_id: str) -> bool:
        records = self._read(container)
        filtered = [record for record in records if record.get("id") != item_id]
        if len(filtered) == len(records):
            return False
        self._write(container, filtered)
        return True


class CosmosStore:
    """Azure Cosmos DB store — fill in credentials to activate."""

    def __init__(self):
        s = get_settings()
        self._endpoint = s.cosmos_endpoint
        self._key = s.cosmos_key
        self._database = s.cosmos_database
        self._client = None

    def _get_client(self):
        if self._client is None:
            from azure.cosmos.aio import CosmosClient
            self._client = CosmosClient(self._endpoint, credential=self._key)
        return self._client

    async def upsert(self, container: str, item: dict) -> dict:
        db = self._get_client().get_database_client(self._database)
        c = db.get_container_client(container)
        return await c.upsert_item(item)

    async def get(self, container: str, item_id: str) -> Optional[dict]:
        db = self._get_client().get_database_client(self._database)
        c = db.get_container_client(container)
        try:
            return await c.read_item(item=item_id, partition_key=item_id)
        except Exception:
            return None

    async def query(self, container: str, partition_key: str, partition_value: str) -> list[dict]:
        db = self._get_client().get_database_client(self._database)
        c = db.get_container_client(container)
        q = f"SELECT * FROM c WHERE c.{partition_key} = @val"
        params = [{"name": "@val", "value": partition_value}]
        items = []
        async for item in c.query_items(query=q, parameters=params):
            items.append(item)
        return items

    async def list_all(self, container: str) -> list[dict]:
        db = self._get_client().get_database_client(self._database)
        c = db.get_container_client(container)
        items = []
        async for item in c.read_all_items():
            items.append(item)
        return items

    async def delete(self, container: str, item_id: str) -> bool:
        db = self._get_client().get_database_client(self._database)
        c = db.get_container_client(container)
        try:
            await c.delete_item(item=item_id, partition_key=item_id)
            return True
        except Exception:
            return False


class AppStorage:
    """
    High-level storage facade used by agents and API routes.
    Delegates to local or Cosmos depending on STORAGE_BACKEND.
    """

    CONTAINERS = [
        "study_plans", "reasoning_trace", "learner_memory",
        "progress_series", "mastery_grid", "eval_results",
        "a2a_audit", "team_capacity", "assessments", "peer_learning_sessions", "manager_interventions",
    ]

    def __init__(self):
        s = get_settings()
        if s.storage_backend == StorageBackend.COSMOS:
            self._store = CosmosStore()
        else:
            self._store = LocalJSONStore(s.store_dir)

    # ── Trace ────────────────────────────────────────────────────────
    async def save_trace(self, trace) -> None:
        await self._store.upsert("reasoning_trace", {"id": trace.run_id, **trace.model_dump()})

    async def get_trace(self, run_id: str) -> Optional[dict]:
        return await self._store.get("reasoning_trace", run_id)

    async def list_traces(self, learner_id: str) -> list[dict]:
        return await self._store.query("reasoning_trace", "learner_id", learner_id)

    # ── Study Plans ─────────────────────────────────────────────────
    async def save_plan(self, plan: dict) -> dict:
        plan.setdefault("id", plan.get("plan_id") or str(uuid.uuid4()))
        return await self._store.upsert("study_plans", plan)

    async def get_plan(self, plan_id: str) -> Optional[dict]:
        return await self._store.get("study_plans", plan_id)

    async def list_plans(self, learner_id: str, cert_id: Optional[str] = None) -> list[dict]:
        records = await self._store.query("study_plans", "learner_id", learner_id)
        if cert_id is not None:
            records = [record for record in records if record.get("cert_id") == cert_id]
        return records

    async def approve_plan(self, plan_id: str, approved_by: str = "human") -> Optional[dict]:
        plan = await self.get_plan(plan_id)
        if plan:
            plan["status"] = "approved"
            plan["approved_by"] = approved_by
            plan["approved_at"] = datetime.now(timezone.utc).isoformat()
            return await self._store.upsert("study_plans", plan)
        return None

    # ── Assessments ─────────────────────────────────────────────────
    async def save_assessment(self, assessment: dict) -> dict:
        assessment.setdefault("id", assessment.get("assessment_id") or str(uuid.uuid4()))
        return await self._store.upsert("assessments", assessment)

    async def get_assessment(self, assessment_id: str) -> Optional[dict]:
        return await self._store.get("assessments", assessment_id)

    async def list_assessments(self, learner_id: str, cert_id: Optional[str] = None) -> list[dict]:
        records = await self._store.query("assessments", "learner_id", learner_id)
        if cert_id is not None:
            records = [record for record in records if record.get("cert_id") == cert_id]
        return records

    # ── Mastery Grid ────────────────────────────────────────────────
    async def save_mastery(self, mastery: dict) -> dict:
        return await self._store.upsert("mastery_grid", mastery)

    async def get_mastery(self, learner_id: str, cert_id: str) -> Optional[dict]:
        records = await self._store.query("mastery_grid", "learner_id", learner_id)
        return next((r for r in records if r.get("cert_id") == cert_id), None)

    # ── Generic ─────────────────────────────────────────────────────
    async def upsert(self, container: str, item: dict) -> dict:
        return await self._store.upsert(container, item)

    async def list_all(self, container: str) -> list[dict]:
        return await self._store.list_all(container)

    async def delete(self, container: str, item_id: str) -> bool:
        return await self._store.delete(container, item_id)

    async def save_peer_learning_session(self, session: dict) -> dict:
        session.setdefault("id", str(uuid.uuid4()))
        return await self._store.upsert("peer_learning_sessions", session)

    async def list_peer_learning_sessions(self, team_id: str) -> list[dict]:
        return await self._store.query("peer_learning_sessions", "team_id", team_id)

    async def delete_peer_learning_session(self, session_id: str) -> bool:
        return await self._store.delete("peer_learning_sessions", session_id)

    async def save_manager_intervention(self, intervention: dict) -> dict:
        intervention.setdefault("id", str(uuid.uuid4()))
        return await self._store.upsert("manager_interventions", intervention)

    async def list_manager_interventions(self, team_id: str) -> list[dict]:
        return await self._store.query("manager_interventions", "team_id", team_id)

    async def delete_manager_intervention(self, intervention_id: str) -> bool:
        return await self._store.delete("manager_interventions", intervention_id)


_storage: Optional[AppStorage] = None


def get_storage() -> AppStorage:
    global _storage
    if _storage is None:
        _storage = AppStorage()
    return _storage
