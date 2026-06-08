"""
Agent factory — loads prompts from /prompts/ and wires up MCP tool executors.
Returns fully configured BaseAgent instances ready to run.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from backend.core.agent import BaseAgent
from backend.core.client import model_supports_tools
from backend.core.mcp_client import get_learn_mcp_client, get_own_mcp_client
from backend.iq.foundry_iq import get_foundry_iq
from backend.models import (
    AssessmentOutput,
    CriticOutput,
    CuratedTopicList,
    EngagementOutput,
    ManagerInsightsOutput,
    StudyPlan,
)
from backend.mcp_server.server import (
    compute_domain_mastery,
    compute_readiness_forecast,
    compute_service_heatmap,
    generate_assessment,
    generate_study_plan,
    validate_citation,
    foundry_iq_search,
    parse_learner_profile,
    compute_progress_series,
    fabric_iq_semantics,
    DomainMasteryInput,
    ForecastInput,
    ServiceHeatmapInput,
    AssessmentInput,
    StudyPlanInput,
    CitationInput,
    FoundryIQInput,
    FabricIQInput,
    LearnerProfileInput,
    ProgressSeriesInput,
)
from backend.models.trace import TraceEvent

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


def _load_prompt(agent_dir: str, version: str = "v1") -> str:
    path = PROMPTS_DIR / agent_dir / f"{version}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    logger.warning("Prompt not found: %s", path)
    return f"You are the {agent_dir} agent for EnterpriseCertIQ."


# ── OpenAI tool schemas for agents that call MCP tools ────────────────────

_OWN_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "parse_learner_profile",
            "description": "Parse and validate a learner profile.",
            "parameters": {
                "type": "object",
                "properties": {
                    "learner_id": {"type": "string"},
                    "cert_target": {"type": "string"},
                    "raw_profile_json": {"type": "string"},
                },
                "required": ["learner_id", "cert_target", "raw_profile_json"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "foundry_iq_search",
            "description": "Search Foundry IQ knowledge base. Returns cited excerpts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "default": 3},
                    "cert_id": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_citation",
            "description": "Validate a citation exists and supports the claim.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string"},
                    "span_id": {"type": "string"},
                    "claim_text": {"type": "string"},
                },
                "required": ["doc_id", "span_id", "claim_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_study_plan",
            "description": "Generate capacity-aware study plan. APPROVAL REQUIRED before publishing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "learner_id": {"type": "string"},
                    "cert_id": {"type": "string"},
                    "curated_topics_json": {"type": "string"},
                    "available_hours_per_week": {"type": "number"},
                    "deadline": {"type": "string"},
                    "weeks": {"type": "integer", "default": 6},
                },
                "required": ["learner_id", "cert_id", "curated_topics_json",
                             "available_hours_per_week", "deadline"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_assessment",
            "description": "Generate timed, cited assessment questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "learner_id": {"type": "string"},
                    "cert_id": {"type": "string"},
                    "domain_focus": {"type": "string"},
                    "question_count": {"type": "integer", "default": 20},
                },
                "required": ["learner_id", "cert_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compute_readiness_forecast",
            "description": "Calibrated pass-probability + CI + weakest topic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "learner_id": {"type": "string"},
                    "cert_id": {"type": "string"},
                    "plan_id": {"type": "string"},
                    "evidence_json": {"type": "string"},
                },
                "required": ["learner_id", "cert_id", "plan_id", "evidence_json"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compute_domain_mastery",
            "description": "Per-domain mastery breakdown from accumulated evidence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "learner_id": {"type": "string"},
                    "cert_id": {"type": "string"},
                    "evidence_json": {"type": "string"},
                },
                "required": ["learner_id", "cert_id", "evidence_json"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compute_service_heatmap",
            "description": "Service-level heatmap within each cert domain.",
            "parameters": {
                "type": "object",
                "properties": {
                    "learner_id": {"type": "string"},
                    "cert_id": {"type": "string"},
                    "evidence_json": {"type": "string"},
                },
                "required": ["learner_id", "cert_id", "evidence_json"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compute_progress_series",
            "description": "Planned-vs-actual progress time series.",
            "parameters": {
                "type": "object",
                "properties": {
                    "learner_id": {"type": "string"},
                    "cert_id": {"type": "string"},
                    "plan_id": {"type": "string"},
                },
                "required": ["learner_id", "cert_id", "plan_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fabric_iq_semantics",
            "description": (
                "Fabric IQ semantic layer: business meaning over the enterprise-learning "
                "ontology. query_type ∈ {readiness_semantics, domain_thresholds, "
                "role_certification_map, cohort_benchmark, intervention_effect, ontology}."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query_type": {"type": "string"},
                    "cert_id": {"type": "string"},
                    "role": {"type": "string"},
                    "evidence_json": {"type": "string"},
                },
                "required": ["query_type"],
            },
        },
    },
]

# Stable index of the Fabric IQ tool within _OWN_TOOLS (appended last).
_FABRIC_TOOL = _OWN_TOOLS[9:10]

_LEARN_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "microsoft_docs_search",
            "description": "Search Microsoft Learn official documentation.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "microsoft_docs_fetch",
            "description": "Fetch full Microsoft Learn documentation page as markdown.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "microsoft_code_sample_search",
            "description": "Search Microsoft Learn for code samples.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "language": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    },
]


async def _exec_own_tool(name: str, **kwargs):
    """Execute an own MCP tool directly (bypasses HTTP for local dev)."""
    if name == "parse_learner_profile":
        return await parse_learner_profile.fn(LearnerProfileInput(**kwargs))
    if name == "foundry_iq_search":
        return await foundry_iq_search.fn(FoundryIQInput(**kwargs))
    if name == "validate_citation":
        return await validate_citation.fn(CitationInput(**kwargs))
    if name == "generate_study_plan":
        return await generate_study_plan.fn(StudyPlanInput(**kwargs))
    if name == "generate_assessment":
        return await generate_assessment.fn(AssessmentInput(**kwargs))
    if name == "compute_readiness_forecast":
        return await compute_readiness_forecast.fn(ForecastInput(**kwargs))
    if name == "compute_domain_mastery":
        return await compute_domain_mastery.fn(DomainMasteryInput(**kwargs))
    if name == "compute_service_heatmap":
        return await compute_service_heatmap.fn(ServiceHeatmapInput(**kwargs))
    if name == "compute_progress_series":
        return await compute_progress_series.fn(ProgressSeriesInput(**kwargs))
    if name == "fabric_iq_semantics":
        return await fabric_iq_semantics.fn(FabricIQInput(**kwargs))
    return {"error": f"Unknown tool: {name}"}


async def _exec_learn_tool(name: str, **kwargs):
    """Execute a Microsoft Learn MCP tool via HTTP."""
    client = get_learn_mcp_client()
    return await client.call_tool(name, kwargs)


def build_agents(on_event=None) -> dict:
    """Build and return all agents keyed by name."""

    def make_agent(name: str, prompt_dir: str, tools: list, model_role: str = "default",
                   temperature: float = 0.3, response_format=None,
                   max_tool_rounds: int = 5) -> BaseAgent:
        agent = BaseAgent(
            name=name,
            instructions=_load_prompt(prompt_dir),
            tools=tools,
            model_role=model_role,
            response_format=response_format,
            temperature=temperature,
            max_tool_rounds=max_tool_rounds,
            on_event=on_event,
            # Every agent has a deterministic tier-3 builder (backend/agents/fallbacks.py).
            supports_fallback=True,
        )
        for tool in _OWN_TOOLS:
            tool_name = tool["function"]["name"]
            agent.register_tool_executor(tool_name, lambda n=tool_name, **kw: _exec_own_tool(n, **kw))
        for tool in _LEARN_TOOLS:
            tool_name = tool["function"]["name"]
            agent.register_tool_executor(tool_name, lambda n=tool_name, **kw: _exec_learn_tool(n, **kw))
        return agent

    intake = make_agent("learner_intake", "learner_intake", _OWN_TOOLS[:1])
    curator = make_agent(
        "curator",
        "curator",
        _OWN_TOOLS[:3] + _LEARN_TOOLS,
        temperature=0.1,
        response_format=CuratedTopicList,
        # Cap grounding rounds: tool-eager models (qwen, gpt-5 family) otherwise
        # loop on MS Learn searches. 4 rounds lets gpt-5-class models ground via
        # Foundry IQ + finalise; if they still don't converge, the deterministic
        # fallback yields valid topics anyway.
        max_tool_rounds=4,
    )
    planner = make_agent(
        "plan_generator",
        "plan_generator",
        _OWN_TOOLS[:4],
        temperature=0.0,
        response_format=StudyPlan,
    )
    # The Critic runs on the reasoning model. Some reasoning models
    # (e.g. phi-4-reasoning) don't support tool-calling — in that case it
    # reasons over the plan/evidence passed in-context and emits objections
    # without tools. Forecast/mastery tools remain available via REST.
    # Critic also gets the Fabric IQ semantic layer (domain thresholds /
    # readiness semantics) so its objections reason over weighted business
    # meaning, not just raw mastery numbers.
    critic_tools = (_OWN_TOOLS[2:3] + _OWN_TOOLS[5:8] + _FABRIC_TOOL
                    if model_supports_tools("reasoning") else [])
    critic = make_agent(
        "readiness_critic", "readiness_critic",
        critic_tools,
        model_role="reasoning",
        temperature=0.0,
        response_format=CriticOutput,
    )
    engagement = make_agent(
        "engagement",
        "engagement",
        _OWN_TOOLS[8:],
        temperature=0.1,
        response_format=EngagementOutput,
    )
    # Manager gets Fabric IQ for semantic team skill-gap meaning + cohort
    # benchmarks alongside profile parsing and grounded retrieval.
    manager = make_agent(
        "manager_insights",
        "manager_insights",
        _OWN_TOOLS[:2] + _FABRIC_TOOL,
        temperature=0.1,
        response_format=ManagerInsightsOutput,
    )
    # Assessment Agent: grounded cited questions + calibrated readiness verdict.
    # Tools: foundry_iq_search (ground next-step), generate_assessment, compute_readiness_forecast.
    assessment = make_agent(
        "assessment",
        "assessment",
        [_OWN_TOOLS[1], _OWN_TOOLS[4], _OWN_TOOLS[5]],
        temperature=0.1,
        response_format=AssessmentOutput,
        max_tool_rounds=3,
    )
    # Retrospective is meta-reasoning over prior failures → use the reasoning model.
    retro = make_agent("retrospective", "retrospective", _OWN_TOOLS[:3], model_role="reasoning")

    return {
        "intake": intake,
        "curator": curator,
        "planner": planner,
        "critic": critic,
        "engagement": engagement,
        "manager": manager,
        "assessment": assessment,
        "retrospective": retro,
    }


def build_audio_agent(on_event=None) -> BaseAgent:
    """Standalone agent that writes a grounded two-host audio study briefing.

    Built on demand by the audio endpoints (not part of the workflow spine). Has a
    deterministic tier-3 fallback so a transcript is produced even with no model.
    """
    from backend.models import PodcastScript

    agent = BaseAgent(
        name="audio_curriculum",
        instructions=_load_prompt("audio_curriculum"),
        tools=[_OWN_TOOLS[1]] + _FABRIC_TOOL,  # foundry_iq_search + fabric_iq_semantics
        model_role="default",
        response_format=PodcastScript,
        temperature=0.4,
        max_tool_rounds=2,
        on_event=on_event,
        supports_fallback=True,
    )
    for tool in _OWN_TOOLS:
        tool_name = tool["function"]["name"]
        agent.register_tool_executor(tool_name, lambda n=tool_name, **kw: _exec_own_tool(n, **kw))
    for tool in _LEARN_TOOLS:
        tool_name = tool["function"]["name"]
        agent.register_tool_executor(tool_name, lambda n=tool_name, **kw: _exec_learn_tool(n, **kw))
    return agent
