"""
Workflow graph orchestrator — runs the 6-agent pipeline with:
  - sequential spine (intake → curator → planner → critic loop → engagement → manager)
  - concurrent fan-out for curator (per cert domain)
  - bounded critique loop (max 2 rounds)
  - conditional retrospective on failure
  - HITL gate before publishing a plan
  - streaming trace events via callback
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional

from backend.core.telemetry import workflow_span
from backend.models.learner import LearnerProfile
from backend.models.trace import ReasoningTrace, TraceEvent, TraceEventType
from backend.mcp_server.server import (
    StudyPlanInput,
    generate_study_plan,
    ForecastInput,
    compute_readiness_forecast,
)

logger = logging.getLogger(__name__)


def _structured_payload(agent_result):
    parsed = getattr(agent_result, "parsed", None)
    if parsed is None:
        return agent_result.content
    if hasattr(parsed, "model_dump"):
        return parsed.model_dump(mode="json")
    return parsed


def _as_text(payload) -> str:
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, indent=2)


def _has_red_objection(payload) -> bool:
    if isinstance(payload, dict):
        objections = payload.get("objections", [])
        return any(
            isinstance(objection, dict) and objection.get("severity") == "red"
            for objection in objections
        )
    return '"severity": "red"' in str(payload)


def _is_valid_plan_payload(payload) -> bool:
    return isinstance(payload, dict) and {
        "plan_id",
        "learner_id",
        "cert_id",
        "created_at",
        "deadline",
        "total_planned_hours",
        "weeks",
    }.issubset(payload.keys())


async def _canonicalize_plan_payload(learner: LearnerProfile, curated_topics, candidate_payload):
    if _is_valid_plan_payload(candidate_payload):
        return candidate_payload, False

    canonical_plan = await generate_study_plan.fn(StudyPlanInput(
        learner_id=learner.learner_id,
        cert_id=learner.cert_target,
        curated_topics_json=json.dumps(curated_topics),
        available_hours_per_week=learner.work_iq_signals.available_study_hours_per_week,
        deadline=learner.deadline,
    ))
    return canonical_plan, True


def _readiness_from_forecast(forecast) -> dict:
    """Deterministic readiness decision from the calibrated forecast.

    Kept separate from the LLM verdict so the workflow's advance/loop-back
    control flow is reliable, not subject to model variance.
    """
    if not isinstance(forecast, dict) or forecast.get("insufficient_evidence"):
        return {"recommendation": "gather_evidence", "verdict": "insufficient_evidence",
                "estimated_exam_score": 0,
                "pass_threshold": (forecast or {}).get("pass_threshold", 700),
                "weakest_topic": ""}
    est = forecast.get("estimated_exam_score", 0)
    thr = forecast.get("pass_threshold", 700)
    ready = est >= thr
    return {"recommendation": "advance" if ready else "remediate",
            "verdict": "ready" if ready else "not_ready",
            "estimated_exam_score": est, "pass_threshold": thr,
            "pass_probability": forecast.get("pass_probability", 0.0),
            "weakest_topic": forecast.get("weakest_topic", "")}


class WorkflowContext:
    def __init__(self, learner: LearnerProfile, run_id: str):
        self.learner = learner
        self.run_id = run_id
        self.trace = ReasoningTrace(
            run_id=run_id,
            learner_id=learner.learner_id,
            cert_id=learner.cert_target,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self.outputs: dict = {}
        self.hitl_pending: bool = False
        self.approved: bool = False

    def add_event(self, event: TraceEvent) -> None:
        self.trace.add_event(event)

    def set_output(self, key: str, value) -> None:
        self.outputs[key] = value


class WorkflowOrchestrator:
    def __init__(
        self,
        intake_agent,
        curator_agent,
        planner_agent,
        critic_agent,
        engagement_agent,
        manager_agent,
        assessment_agent=None,
        retrospective_agent=None,
        storage=None,
        max_critique_rounds: int = 2,
    ):
        self.intake = intake_agent
        self.curator = curator_agent
        self.planner = planner_agent
        self.critic = critic_agent
        self.engagement = engagement_agent
        self.manager = manager_agent
        self.assessment = assessment_agent
        self.retrospective = retrospective_agent
        self.storage = storage
        self.max_critique_rounds = max_critique_rounds

    async def run(
        self,
        learner: LearnerProfile,
        on_event: Optional[Callable[[TraceEvent], None]] = None,
        run_id: Optional[str] = None,
    ) -> WorkflowContext:
        run_id = run_id or str(uuid.uuid4())
        ctx = WorkflowContext(learner=learner, run_id=run_id)

        def emit(event: TraceEvent):
            ctx.add_event(event)
            if on_event:
                on_event(event)

        # Route per-agent events (AGENT_START, TOOL_CALL, CRITIC_OBJECTION, …)
        # into the persisted trace too — not just the live SSE stream — so the
        # full reasoning trace survives a page reload / trace replay.
        for agent in (self.intake, self.curator, self.planner, self.critic,
                      self.engagement, self.manager, self.assessment, self.retrospective):
            if agent is not None:
                agent.on_event = emit

        def make_event(event_type: TraceEventType, agent: str, data: dict) -> TraceEvent:
            return TraceEvent(
                event_id=str(uuid.uuid4()),
                run_id=run_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                event_type=event_type,
                agent_name=agent,
                data=data,
            )

        with workflow_span(run_id, learner.learner_id, learner.cert_target):
            emit(make_event(TraceEventType.WORKFLOW_START, "orchestrator", {
                "learner_id": learner.learner_id,
                "cert_target": learner.cert_target,
            }))

            # Shared context passed to every agent — powers the deterministic
            # tier-3 fallback (backend/agents/fallbacks.py) when the model is
            # unavailable or AGENT_FALLBACK_MODE=force.
            base_ctx = {
                "learner_obj": learner,
                "learner_id": learner.learner_id,
                "cert_id": learner.cert_target,
                "team_id": learner.team_id,
            }

            # ── Stage 1: Learner Intake ──────────────────────────────────────
            intake_result = await self.intake.run(
                messages=[{"role": "user", "content": f"Parse and validate learner profile: {learner.model_dump_json()}"}],
                run_id=run_id,
                context=base_ctx,
            )
            ctx.set_output("intake", intake_result)

            # ── Stage 2: Learning Path Curator ──────────────────────────────
            curator_result = await self.curator.run(
                messages=[{
                    "role": "user",
                    "content": (
                        f"Learner profile:\n{intake_result.content}\n\n"
                        f"Cert target: {learner.cert_target}\n"
                        "Map this cert to skill topics. Retrieve approved content and "
                        "Microsoft Learn paths. Cite every recommendation."
                    )
                }],
                run_id=run_id,
                context=base_ctx,
            )
            ctx.set_output("curator", curator_result)
            curated_topics = _structured_payload(curator_result)

            # ── Stage 3: Study Plan Generator → Critic loop ─────────────────
            plan_draft = await self.planner.run(
                messages=[{
                    "role": "user",
                    "content": (
                        f"Learner: {learner.model_dump_json()}\n\n"
                        f"Curated topics:\n{_as_text(curated_topics)}\n\n"
                        "Generate a capacity-aware weekly study plan. "
                        "Return JSON matching the StudyPlan schema."
                    )
                }],
                run_id=run_id,
                context={**base_ctx, "curated_topics": curated_topics},
            )
            ctx.set_output("plan_draft", plan_draft)
            plan_payload, synthesized_plan = await _canonicalize_plan_payload(
                learner,
                curated_topics,
                _structured_payload(plan_draft),
            )
            if synthesized_plan:
                emit(make_event(TraceEventType.TOOL_RESULT, "plan_generator", {
                    "tool": "generate_study_plan",
                    "result_length": len(str(plan_payload)),
                    "result": plan_payload,
                    "synthesized": True,
                }))

            # Fabric IQ: weighted domain thresholds give the Critic semantic
            # business meaning (which domains carry the most leverage) even if
            # its model can't call tools.
            from backend.iq.fabric_iq import get_fabric_iq
            domain_thresholds = get_fabric_iq().get_domain_thresholds(learner.cert_target)

            critique_history = [plan_payload]
            for round_n in range(1, self.max_critique_rounds + 1):
                critic_result = await self.critic.run(
                    messages=[{
                        "role": "user",
                        "content": (
                            f"Learner: {learner.model_dump_json()}\n\n"
                            f"Fabric IQ weighted domain thresholds (highest leverage first):\n"
                            f"{_as_text(domain_thresholds)}\n\n"
                            f"Study plan (round {round_n}):\n{_as_text(critique_history[-1])}\n\n"
                            "Identify weaknesses: under-allocated high-leverage domains, schedule "
                            "conflicts, prerequisite ordering. Weight objections by domain leverage. "
                            "Return objections as JSON list with severity red/amber, description, "
                            "recommendation, citation."
                        )
                    }],
                    run_id=run_id,
                    context={**base_ctx, "plan": critique_history[-1]},
                )
                ctx.set_output(f"critic_round_{round_n}", critic_result)
                critic_payload = _structured_payload(critic_result)
                critique_history.append(critic_payload)

                if not _has_red_objection(critic_payload):
                    logger.info("Critic satisfied after round %d", round_n)
                    break

                revised = await self.planner.run(
                    messages=[{
                        "role": "user",
                        "content": (
                            f"Revise the study plan to address these Critic objections:\n"
                            f"{_as_text(critic_payload)}\n\n"
                            f"Original plan:\n{critique_history[-2]}"
                        )
                    }],
                    run_id=run_id,
                    context={**base_ctx, "curated_topics": curated_topics},
                )
                ctx.set_output(f"plan_revision_{round_n}", revised)
                revised_payload, synthesized_revision = await _canonicalize_plan_payload(
                    learner,
                    curated_topics,
                    _structured_payload(revised),
                )
                if synthesized_revision:
                    emit(make_event(TraceEventType.TOOL_RESULT, "plan_generator", {
                        "tool": "generate_study_plan",
                        "result_length": len(str(revised_payload)),
                        "result": revised_payload,
                        "synthesized": True,
                    }))
                critique_history.append(revised_payload)

            ctx.set_output("final_plan", critique_history[-1])

            # ── Stage 4: HITL gate ─────────────────────────────────────────
            # The plan stays in `draft` status and is never marked published
            # until a human calls /api/plans/approve. The Engagement and
            # Manager stages below run on the draft to produce *advisory
            # previews* so the reviewer has full context at approval time.
            final_payload = critique_history[-1]
            draft_plan_id = (
                final_payload.get("plan_id") if isinstance(final_payload, dict) else None
            )
            emit(make_event(TraceEventType.HITL_REQUEST, "orchestrator", {
                "plan_id": draft_plan_id,
                "plan_status": "draft",
                "plan_summary": _as_text(final_payload)[:300],
                "message": (
                    "Draft plan ready for human approval. It remains a draft "
                    "(not published) until approved. Engagement and Manager "
                    "outputs below are advisory previews pending that approval."
                ),
            }))
            ctx.hitl_pending = True
            ctx.trace.final_status = "hitl_pending"

            # ── Stage 5: Engagement Agent ──────────────────────────────────
            engagement_result = await self.engagement.run(
                messages=[{
                    "role": "user",
                    "content": (
                        f"Work IQ signals: {learner.work_iq_signals.model_dump_json()}\n\n"
                        f"Study plan:\n{_as_text(critique_history[-1])}\n\n"
                        "Suggest study reminder times. Identify capacity conflicts. "
                        "Return engagement schedule as JSON."
                    )
                }],
                run_id=run_id,
                context=base_ctx,
            )
            ctx.set_output("engagement", engagement_result)
            engagement_payload = _structured_payload(engagement_result)

            # ── Stage 6: Assessment Agent → readiness verdict + loop-back ───
            # Authoritative readiness comes from the calibrated forecast; the
            # Assessment Agent adds grounded cited questions + a narrative verdict.
            evidence = (
                learner.prior_assessment_evidence.model_dump()
                if learner.prior_assessment_evidence else {}
            )
            forecast = await compute_readiness_forecast.fn(ForecastInput(
                learner_id=learner.learner_id,
                cert_id=learner.cert_target,
                plan_id=draft_plan_id or "draft",
                evidence_json=json.dumps(evidence),
            ))

            if self.assessment:
                assessment_result = await self.assessment.run(
                    messages=[{
                        "role": "user",
                        "content": (
                            f"Learner: {learner.model_dump_json()}\n\n"
                            f"Calibrated readiness forecast:\n{_as_text(forecast)}\n\n"
                            f"Study plan:\n{_as_text(critique_history[-1])[:600]}\n\n"
                            "Generate grounded, cited practice questions; evaluate readiness; "
                            "and recommend advance / remediate / gather_evidence. Ground the "
                            "next-step certification recommendation with foundry_iq_search. "
                            "Return the AssessmentOutput JSON."
                        )
                    }],
                    run_id=run_id,
                    context={**base_ctx, "forecast": forecast},
                )
                ctx.set_output("assessment", assessment_result)
                assessment_payload = _structured_payload(assessment_result)
            else:
                assessment_payload = None

            decision = _readiness_from_forecast(forecast)
            ctx.set_output("readiness_decision", decision)

            if decision["recommendation"] == "advance":
                next_step = ""
                if isinstance(assessment_payload, dict):
                    next_step = assessment_payload.get("next_step", "")
                if not next_step:
                    # Fabric IQ ontology is the single source of truth for the
                    # 'advances_to' relationship.
                    nxt = get_fabric_iq().get_next_certification(learner.cert_target)
                    next_step = (f"Recommend {nxt} as the next certification."
                                 if nxt else "Recommend an advanced certification next.")
                emit(make_event(TraceEventType.READINESS_ADVANCE, "assessment", {
                    "verdict": "ready",
                    "estimated_exam_score": decision["estimated_exam_score"],
                    "pass_threshold": decision["pass_threshold"],
                    "next_step": next_step,
                    "message": (
                        f"Readiness met ({decision['estimated_exam_score']}/"
                        f"{decision['pass_threshold']}). {next_step}"
                    ),
                }))
            elif decision["recommendation"] == "remediate":
                weak = decision.get("weakest_topic", "") or "the weakest domain"
                emit(make_event(TraceEventType.READINESS_LOOPBACK, "assessment", {
                    "verdict": "not_ready",
                    "estimated_exam_score": decision["estimated_exam_score"],
                    "pass_threshold": decision["pass_threshold"],
                    "weak_area": weak,
                    "message": (
                        f"Below threshold ({decision['estimated_exam_score']}/"
                        f"{decision['pass_threshold']}). Looping back to strengthen: {weak}."
                    ),
                }))
                # Bounded loop-back: one focused remediation re-plan on the weak area.
                remediation = await self.planner.run(
                    messages=[{
                        "role": "user",
                        "content": (
                            f"The learner is NOT yet ready (weakest area: {weak}). Revise the "
                            f"study plan to add focused remediation on '{weak}' before the exam.\n\n"
                            f"Current plan:\n{_as_text(critique_history[-1])}"
                        )
                    }],
                    run_id=run_id,
                    context={**base_ctx, "curated_topics": curated_topics},
                )
                rem_payload, rem_synth = await _canonicalize_plan_payload(
                    learner, curated_topics, _structured_payload(remediation),
                )
                if rem_synth:
                    emit(make_event(TraceEventType.TOOL_RESULT, "plan_generator", {
                        "tool": "generate_study_plan",
                        "result_length": len(str(rem_payload)),
                        "result": rem_payload, "synthesized": True, "remediation": True,
                    }))
                critique_history.append(rem_payload)
                ctx.set_output("final_plan", critique_history[-1])
            else:  # gather_evidence
                emit(make_event(TraceEventType.READINESS_LOOPBACK, "assessment", {
                    "verdict": "insufficient_evidence",
                    "message": (
                        "Insufficient evidence to forecast readiness — complete at least one "
                        "assessment before advancing. Looping back to gather evidence."
                    ),
                }))

            # ── Stage 7: Manager Insights ──────────────────────────────────
            manager_result = await self.manager.run(
                messages=[{
                    "role": "user",
                    "content": (
                        f"Team ID: {learner.team_id}\n"
                        f"Learner summary:\n{intake_result.content}\n\n"
                        f"Plan summary:\n{_as_text(critique_history[-1])[:500]}\n\n"
                        f"Engagement:\n{_as_text(engagement_payload)}\n\n"
                        f"Readiness decision: {decision['verdict']} "
                        f"({decision['estimated_exam_score']}/{decision['pass_threshold']})\n\n"
                        "Produce manager-level insights: team readiness summary, "
                        "risk areas, peer-learning pairs. Never expose individual scores "
                        "that could affect employment decisions."
                    )
                }],
                run_id=run_id,
                context=base_ctx,
            )
            ctx.set_output("manager", manager_result)

            # ── Stage 8: Retrospective (if prior failures exist) ───────────
            if learner.has_prior_failures and self.retrospective:
                retro_result = await self.retrospective.run(
                    messages=[{
                        "role": "user",
                        "content": (
                            f"Prior attempts:\n{[a.model_dump() for a in learner.prior_attempts]}\n\n"
                            f"Current plan:\n{_as_text(critique_history[-1])[:500]}\n\n"
                            "Investigate what went wrong in the prior attempt: "
                            "retrieval quality, plan quality, engagement gap, or real skill gap. "
                            "Write a postmortem and recovery recommendations."
                        )
                    }],
                    run_id=run_id,
                    context=base_ctx,
                )
                ctx.set_output("retrospective", retro_result)

            ctx.trace.completed_at = datetime.now(timezone.utc).isoformat()
            ctx.trace.final_status = "hitl_pending"

            if self.storage:
                await self.storage.save_trace(ctx.trace)

            emit(make_event(TraceEventType.WORKFLOW_COMPLETE, "orchestrator", {
                "stages_completed": list(ctx.outputs.keys()),
                "hitl_pending": ctx.hitl_pending,
            }))

        return ctx
