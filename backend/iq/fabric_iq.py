"""
Fabric IQ integration — the semantic layer.

The three Microsoft IQ layers answer different questions in this app:

  Foundry IQ  →  "What approved content exists?"          (grounded retrieval)
  Work IQ     →  "What is happening in a person's work?"  (work-context signals)
  Fabric IQ   →  "What do these entities, rules, and metrics MEAN for
                  enterprise learning decisions?"          (semantic / ontology)

Fabric IQ is Microsoft's semantic foundation: an ontology that connects people,
roles, certifications, skill domains, thresholds, and outcomes into unified
business entities and relationships so people *and* agents can reason over
business meaning rather than raw JSON.

Local mode (default):
    Builds an in-memory ontology from the synthetic datasets
    (cert_structures.json, learners.json, teams.json, cohort_outcomes.json)
    and answers semantic queries with weight- and cohort-aware logic.

Azure mode (FABRIC_IQ_ENDPOINT set):
    Would query a Microsoft Fabric semantic model / OneLake lakehouse.
    Not provisioned in this repo yet — falls back to the local ontology so the
    runtime contract is identical. See docs/azure-ai-foundry-migration.md Phase 5.

Multi-account note: Fabric can live in a *different* Azure account/tenant than Foundry.
When the Azure data binding is built it should authenticate with
`backend.core.azure_credentials.get_service_credential("fabric")`, which returns a
ClientSecretCredential scoped to FABRIC_TENANT_ID/CLIENT_ID/CLIENT_SECRET (its own
account) or DefaultAzureCredential. See docs/multi-account-azure.md.
"""
from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from config.settings import get_settings

logger = logging.getLogger(__name__)

AI_DISCLOSURE = "Semantic interpretation via Fabric IQ ontology (synthetic data)"

# Certification advancement chain (role → next milestone). Part of the ontology's
# "role recommends certification" / "certification advances to certification" rules.
_ADVANCEMENT = {
    "AZ-204": "AZ-305",
    "AZ-400": "AZ-500",
    "DP-203": "DP-300",
    "AZ-305": "AZ-400",
    "AI-900": "AI-102",   # fundamentals → associate
    "AI-102": "AZ-305",   # AI engineer → solutions architect
    "DP-100": "DP-203",   # data scientist → data engineer
    "SC-100": "",          # already expert tier
    "MS-102": "",          # already expert tier
}

# Default per-domain minimum mastery target. A cert's passing_score (e.g. 700/1000)
# is the *overall* bar; semantically a learner needs ~that ratio in every weighted
# domain, with high-weight domains carrying more leverage on the final outcome.
_DEFAULT_PASS_RATIO = 0.70


def _priority_for_weight(weight_pct: float) -> str:
    if weight_pct >= 25:
        return "high"
    if weight_pct >= 15:
        return "medium"
    return "low"


# Connective + ultra-generic tokens that appear across many domain names and would
# otherwise cause false skill→domain matches (e.g. matching on "and" or "azure").
_STOPWORDS = {
    "and", "or", "the", "to", "for", "of", "a", "an", "in", "on", "with", "by",
    "azure", "microsoft", "solutions", "solution", "develop", "design", "implement",
    "implementing", "designing", "manage", "configure", "plan", "strategy",
    "third", "party", "use", "using",
}


def _meaningful_tokens(text: str) -> set[str]:
    """Lower-cased tokens with stopwords and very short tokens removed."""
    return {
        t for t in re.findall(r"[a-z0-9]+", str(text).lower())
        if len(t) > 3 and t not in _STOPWORDS
    }


def _skill_matches_domain(skill: str, domain_name: str, services: list[str]) -> bool:
    """True if an evidence key maps to a domain — exact name match first, then a
    meaningful-token overlap against the domain name + its services."""
    if skill.strip().casefold() == domain_name.strip().casefold():
        return True
    skill_tokens = _meaningful_tokens(skill)
    domain_tokens = _meaningful_tokens(domain_name + " " + " ".join(services))
    return bool(skill_tokens & domain_tokens)


class FabricIQClient:
    """Semantic layer over the enterprise-learning ontology."""

    def __init__(self) -> None:
        self.s = get_settings()
        self._certs: dict = {}
        self._learners: list[dict] = []
        self._teams: list[dict] = []
        self._cohort: list[dict] = []
        self._loaded = False

    # ── Ontology loading ────────────────────────────────────────────────
    def _data_path(self, *parts: str) -> Path:
        return Path(self.s.data_dir).joinpath(*parts)

    def _load(self) -> None:
        if self._loaded:
            return
        synthetic = self._data_path("synthetic")
        self._certs = self._read_json(synthetic / "cert_structures.json", {})
        self._learners = self._read_json(synthetic / "learners.json", [])
        self._teams = self._read_json(synthetic / "teams.json", [])
        self._cohort = self._read_json(synthetic / "cohort_outcomes.json", [])
        self._loaded = True
        logger.info(
            "Fabric IQ (local ontology): %d certs, %d learners, %d teams, %d cohort rows",
            len(self._certs), len(self._learners), len(self._teams), len(self._cohort),
        )

    @staticmethod
    def _read_json(path: Path, default):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("Fabric IQ: could not read %s: %s", path, e)
            return default

    # ── Azure (Microsoft Fabric IQ) connection ──────────────────────────
    def _azure_enabled(self) -> bool:
        """True when FABRIC_IQ_ENDPOINT targets a real Fabric workspace (not 'local')."""
        ep = (self.s.fabric_iq_endpoint or "").strip()
        return bool(ep) and ep.lower() != "local"

    def _fabric_token(self) -> str:
        """Entra token for the Fabric data plane. Uses get_service_credential('fabric'),
        so Fabric may live in a different account/tenant than Foundry (FABRIC_TENANT_ID/
        CLIENT_ID/CLIENT_SECRET) — see docs/multi-account-azure.md."""
        from backend.core.azure_credentials import get_service_credential
        cred = get_service_credential("fabric")
        return cred.get_token("https://api.fabric.microsoft.com/.default").token

    def _query_fabric(self, intent: str, params: dict, question: str) -> Optional[dict]:
        """Send a semantic query to the Fabric IQ data agent (NL2Ontology) and return its
        JSON answer, or None on any failure (→ caller falls back to the local ontology).

        Connection-ready: no-ops to None until FABRIC_IQ_ENDPOINT points at a real Fabric
        workspace. Mirrors FoundryIQClient._search_azure — a branch + a real authenticated
        call + a graceful local fallback. The request path/payload follow the Fabric data
        agent (preview); finalize field names against your live workspace.
        """
        if not self._azure_enabled():
            return None
        try:
            import httpx
            endpoint = self.s.fabric_iq_endpoint.rstrip("/")
            workspace = self.s.fabric_iq_workspace
            token = self._fabric_token()
            with httpx.Client(timeout=20) as c:
                r = c.post(
                    f"{endpoint}/v1/workspaces/{workspace}/aiservices/dataagent/query",
                    json={"intent": intent, "parameters": params, "question": question},
                    headers={"Authorization": f"Bearer {token}",
                             "Content-Type": "application/json"},
                )
                r.raise_for_status()
                return r.json()
        except Exception as e:
            logger.error("Fabric IQ Azure query failed, falling back to local ontology: %s", e)
            return None

    # ── SKU-free path: Lakehouse SQL analytics endpoint (works on the Fabric Trial) ──
    def _sql_enabled(self) -> bool:
        return bool(self.s.fabric_sql_endpoint and self.s.fabric_sql_database)

    def _query_fabric_sql(self, sql: str, params: tuple = ()) -> Optional[list[dict]]:
        """Query the Lakehouse SQL analytics endpoint (T-SQL over the OneLake Delta tables)
        with an Entra token — no data agent / paid F2 required. Returns rows as dicts, or
        None on any failure (→ caller falls back to local). Needs pyodbc + ODBC Driver 18.
        """
        if not self._sql_enabled():
            return None
        try:
            import struct
            import pyodbc
            from backend.core.azure_credentials import get_service_credential
            token = get_service_credential("fabric").get_token(
                "https://database.windows.net/.default").token
            tok = token.encode("utf-16-le")
            token_struct = struct.pack(f"<I{len(tok)}s", len(tok), tok)
            conn_str = (
                "Driver={ODBC Driver 18 for SQL Server};"
                f"Server={self.s.fabric_sql_endpoint};Database={self.s.fabric_sql_database};"
                "Encrypt=yes;TrustServerCertificate=no;"
            )
            with pyodbc.connect(conn_str, attrs_before={1256: token_struct}) as conn:  # 1256 = SQL_COPT_SS_ACCESS_TOKEN
                cur = conn.cursor()
                cur.execute(sql, params)
                cols = [c[0] for c in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
        except Exception as e:
            logger.error("Fabric IQ SQL endpoint query failed, falling back to local: %s", e)
            return None

    @staticmethod
    def _coerce_thresholds(answer: Optional[dict]) -> Optional[list[dict]]:
        """Map a Fabric IQ response into our threshold shape; return None if it doesn't
        conform so the caller falls back to the local ontology (never returns a wrong shape)."""
        if not isinstance(answer, dict):
            return None
        rows = answer.get("domains") or answer.get("thresholds") or answer.get("value")
        if not isinstance(rows, list) or not rows:
            return None
        out: list[dict] = []
        for d in rows:
            if not isinstance(d, dict) or "weight_pct" not in d:
                return None  # shape mismatch → local fallback
            weight = float(d.get("weight_pct", 0))
            out.append({
                "domain_id": d.get("domain_id", ""),
                "name": d.get("name", ""),
                "weight_pct": weight,
                "leverage": round(weight / 100, 3),
                "minimum_mastery": float(d.get("minimum_mastery", _DEFAULT_PASS_RATIO)),
                "priority": d.get("priority") or _priority_for_weight(weight),
                "services": d.get("services", []),
            })
        return out

    # ── Semantic queries ────────────────────────────────────────────────

    def describe_ontology(self) -> dict:
        """Return the entity/relationship/rule model — used for demo transparency."""
        return {
            "entities": [
                "Learner", "Team", "Manager", "Role", "Certification",
                "SkillDomain", "ReadinessForecast", "Intervention", "PeerSession",
            ],
            "relationships": [
                "learner belongs_to team",
                "learner has role",
                "role recommends certification",
                "certification contains skill_domain",
                "skill_domain has weight and minimum_mastery",
                "certification advances_to certification",
                "intervention targets learner",
                "peer_session improves weak skill_domain",
                "readiness depends_on evidence and work_context",
            ],
            "rules": [
                f"A learner needs ~{int(_DEFAULT_PASS_RATIO * 100)}% mastery in each weighted domain.",
                "High-weight domains carry more leverage on the final outcome.",
                "Insufficient evidence is never treated as readiness.",
            ],
            "ai_disclosure": AI_DISCLOSURE,
        }

    def get_role_certification_map(self, role: Optional[str] = None) -> dict:
        """role → {primary cert, recommended_hours, next_cert}. The ontology's
        'role recommends certification' relationship."""
        self._load()
        mapping: dict[str, dict] = {}
        for cert_id, cert in self._certs.items():
            r = cert.get("role", "Unknown")
            mapping.setdefault(r, {
                "role": r,
                "primary_certification": cert_id,
                "recommended_hours": cert.get("recommended_study_hours", 20),
                "next_certification": _ADVANCEMENT.get(cert_id, ""),
            })
        if role:
            return mapping.get(role, {
                "role": role, "primary_certification": "", "recommended_hours": 20,
                "next_certification": "",
            })
        return mapping

    def get_next_certification(self, cert_id: str) -> str:
        """The 'advances_to' edge — single source of truth for the workflow."""
        return _ADVANCEMENT.get(cert_id, "")

    def get_domain_thresholds(self, cert_id: str) -> list[dict]:
        """Per-domain semantic thresholds: weight, leverage, minimum mastery, priority.

        Azure (Fabric IQ) path first when FABRIC_IQ_ENDPOINT is set; falls back to the
        local ontology on any failure or shape mismatch. `_evidence_domains`,
        `get_readiness_semantics`, and `get_team_skill_gap_summary` all build on this, so
        routing this one method grounds the whole readiness chain in Fabric IQ.
        """
        self._load()
        # 1) SKU-free: Lakehouse SQL analytics endpoint (Trial-friendly).
        if self._sql_enabled():
            rows = self._query_fabric_sql(
                "SELECT domain_id, name, weight_pct, minimum_mastery "
                "FROM cert_domains WHERE cert_id = ?", (cert_id,))
            mapped = self._coerce_thresholds({"domains": rows} if rows else None)
            if mapped:
                return mapped
        # 2) Fabric data agent (needs paid F2+ capacity).
        if self._azure_enabled():
            mapped = self._coerce_thresholds(self._query_fabric(
                intent="domain_thresholds",
                params={"cert_id": cert_id},
                question=f"List the weighted skill domains and minimum mastery for certification {cert_id}.",
            ))
            if mapped:
                return mapped
        # 3) Local ontology (default / fallback).
        cert = self._certs.get(cert_id, {})
        pass_ratio = cert.get("passing_score", 700) / 1000
        thresholds = []
        for d in cert.get("domains", []):
            weight = float(d.get("weight_pct", 0))
            thresholds.append({
                "domain_id": d.get("domain_id", ""),
                "name": d.get("name", ""),
                "weight_pct": weight,
                "leverage": round(weight / 100, 3),
                "minimum_mastery": round(pass_ratio, 2),
                "priority": _priority_for_weight(weight),
                "services": d.get("services", []),
            })
        return thresholds

    def _evidence_domains(self, cert_id: str, evidence: dict) -> list[dict]:
        """Map generic evidence skill-keys (compute/networking/…) onto a cert's
        weighted domains by matching keys against each domain's name + services."""
        thresholds = self.get_domain_thresholds(cert_id)
        scores = {k: float(v) for k, v in (evidence or {}).items()
                  if isinstance(v, (int, float))}
        out = []
        for d in thresholds:
            matched = [v for k, v in scores.items()
                       if _skill_matches_domain(k, d["name"], d["services"])]
            avg = round(sum(matched) / len(matched), 3) if matched else None
            gap = round(max(0.0, d["minimum_mastery"] - avg), 3) if avg is not None else None
            out.append({
                **d,
                "avg_mastery": avg,
                "evidence_count": len(matched),
                "gap": gap,
                "priority_gap": round(gap * d["leverage"], 4) if gap is not None else None,
            })
        return out

    def get_readiness_semantics(self, cert_id: str, evidence: dict) -> dict:
        """Interpret a learner's evidence against the cert's domain thresholds."""
        self._load()
        domains = self._evidence_domains(cert_id, evidence)
        scored = [d for d in domains if d["avg_mastery"] is not None]
        if not scored:
            return {
                "cert_id": cert_id,
                "insufficient_evidence": True,
                "domains": domains,
                "message": "No domain-level evidence — readiness cannot be interpreted.",
                "ai_disclosure": AI_DISCLOSURE,
            }
        gaps = [d for d in scored if (d["gap"] or 0) > 0]
        gaps.sort(key=lambda d: d["priority_gap"] or 0, reverse=True)
        weighted_mastery = round(
            sum(d["avg_mastery"] * d["leverage"] for d in scored)
            / max(sum(d["leverage"] for d in scored), 1e-9), 3
        )
        return {
            "cert_id": cert_id,
            "insufficient_evidence": False,
            "weighted_mastery": weighted_mastery,
            "meets_overall_bar": weighted_mastery >= _DEFAULT_PASS_RATIO,
            "highest_leverage_gap": gaps[0] if gaps else None,
            "domains": domains,
            "ai_disclosure": AI_DISCLOSURE,
        }

    def get_cohort_benchmark(self, cert_id: Optional[str] = None) -> dict:
        """Aggregate outcomes from the synthetic cohort fact table."""
        self._load()
        rows = [r for r in self._cohort
                if cert_id is None or r.get("cert_id") == cert_id]
        if not rows:
            return {"cert_id": cert_id, "sample_size": 0,
                    "message": "No cohort history available.", "ai_disclosure": AI_DISCLOSURE}
        passes = [r for r in rows if r.get("exam_outcome") == "Pass"]
        avg_score = sum(r.get("practice_score_avg", 0) for r in rows) / len(rows)
        avg_hours = sum(r.get("hours_studied", 0) for r in rows) / len(rows)
        # Cohort rule: learners with >=20 study hours AND <=18 meeting hours pass more.
        protected = [r for r in rows
                     if r.get("hours_studied", 0) >= 20 and r.get("meeting_hours_pw", 99) <= 18]
        protected_pass = (sum(1 for r in protected if r.get("exam_outcome") == "Pass")
                          / len(protected)) if protected else None
        return {
            "cert_id": cert_id,
            "sample_size": len(rows),
            "pass_rate": round(len(passes) / len(rows), 2),
            "avg_practice_score": round(avg_score, 1),
            "avg_hours_studied": round(avg_hours, 1),
            "protected_capacity_pass_rate": round(protected_pass, 2) if protected_pass is not None else None,
            "insight": (
                "Learners with >=20 study hours and <=18 meeting hours/week pass at a "
                "higher rate than the cohort average."
            ),
            "ai_disclosure": AI_DISCLOSURE,
        }

    def get_intervention_effectiveness(self, cert_id: Optional[str] = None) -> dict:
        """Cohort-derived estimate of how much protecting capacity lifts pass odds.
        Feeds the manager what-if narrative with a semantic, data-anchored prior."""
        bench = self.get_cohort_benchmark(cert_id)
        base = bench.get("pass_rate")
        protected = bench.get("protected_capacity_pass_rate")
        lift = round(protected - base, 2) if (base is not None and protected is not None) else None
        return {
            "cert_id": cert_id,
            "baseline_pass_rate": base,
            "protected_capacity_pass_rate": protected,
            "estimated_lift": lift,
            "recommended_lever": (
                "Protect study time / reduce meeting load — the cohort shows this is the "
                "strongest controllable driver of certification success."
            ),
            "sample_size": bench.get("sample_size", 0),
            "ai_disclosure": AI_DISCLOSURE,
        }

    def get_team_skill_gap_summary(
        self,
        team_id: str,
        evidence_by_learner: dict[str, dict],
        member_certs: Optional[dict[str, str]] = None,
        team_size: Optional[int] = None,
    ) -> dict:
        """Semantic, team-level skill-gap analysis.

        Members may target different certifications and their evidence may be
        keyed by skill or by domain name, so we aggregate each key across the
        team and rank gaps by **gap × leverage × coverage** — where coverage is
        the share of team members who actually carry that gap. This stops a
        single member's weak mock from masquerading as a team-wide problem.
        """
        self._load()
        member_certs = member_certs or {}
        team_size = team_size or len(evidence_by_learner) or 1

        # 1. Team scores per evidence key (skill or domain name).
        key_scores: dict[str, list[float]] = {}
        for evidence in evidence_by_learner.values():
            for key, value in (evidence or {}).items():
                if isinstance(value, (int, float)):
                    key_scores.setdefault(key, []).append(float(value))

        # 2. Reverse index: which (cert, domain, weight) does each key affect?
        def affected_by(skill: str) -> list[dict]:
            hits = []
            for cert_id in set(member_certs.values()) or set(self._certs.keys()):
                for d in self.get_domain_thresholds(cert_id):
                    if _skill_matches_domain(skill, d["name"], d["services"]):
                        hits.append({"cert_id": cert_id, "domain": d["name"],
                                     "weight_pct": d["weight_pct"]})
            return hits

        gaps = []
        for skill, values in key_scores.items():
            avg = sum(values) / len(values)
            gap = max(0.0, _DEFAULT_PASS_RATIO - avg)
            # learners who individually fall short on this key
            short = sum(1 for v in values if v < _DEFAULT_PASS_RATIO)
            coverage = round(short / team_size, 3)
            affects = affected_by(skill)
            leverage = max((a["weight_pct"] for a in affects), default=0) / 100
            gaps.append({
                "skill": skill,
                "team_avg_mastery": round(avg, 3),
                "gap": round(gap, 3),
                "coverage": coverage,                 # share of team carrying the gap
                "members_short": short,
                "priority_gap": round(gap * leverage * coverage, 4),
                "learner_count": len(values),
                "affects": affects,
            })
        gaps.sort(key=lambda g: g["priority_gap"], reverse=True)
        ranked = [g for g in gaps if g["gap"] > 0 and g["coverage"] > 0][:3]

        top = ranked[0] if ranked else None
        if top:
            affects_str = ", ".join(
                f"{a['cert_id']} {a['domain']} ({int(a['weight_pct'])}%)"
                for a in top["affects"][:2]
            ) or "no weighted domain"
            narrative = (
                f"Top priority gap for {team_id}: '{top['skill']}' "
                f"(team avg {int(top['team_avg_mastery'] * 100)}%, affects "
                f"{top['members_short']} of {team_size} members), weighing on {affects_str}."
            )
        else:
            narrative = f"No team-wide skill gaps detected for {team_id}."

        return {
            "team_id": team_id,
            "team_size": team_size,
            "top_priority_gaps": ranked,
            "all_skill_gaps": gaps,
            "narrative": narrative,
            "ai_disclosure": AI_DISCLOSURE,
        }


@lru_cache(maxsize=1)
def get_fabric_iq() -> FabricIQClient:
    return FabricIQClient()
