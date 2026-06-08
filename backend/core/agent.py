"""
Base agent class — thin wrapper around openai.AsyncOpenAI that handles:
  - tool-call loop (MCP tools as OpenAI functions)
  - structured output parsing
  - trace event emission
  - bounded retry on transient errors
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional, Type

from openai import AsyncOpenAI
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.core.client import ensure_model_loaded, get_client, get_model_name
from backend.core.telemetry import agent_span, span
from backend.evals.groundedness import evaluate_async, get_eval_model_config
from backend.middleware.pipeline import apply_pipeline
from backend.models.trace import TraceEvent, TraceEventType

logger = logging.getLogger(__name__)


class AgentResult(BaseModel):
    agent_name: str
    content: str
    parsed: Optional[Any] = None
    tool_calls_made: list[dict] = []
    token_usage: dict = {}


class BaseAgent:
    def __init__(
        self,
        name: str,
        instructions: str,
        tools: Optional[list[dict]] = None,
        response_format: Optional[Type[BaseModel]] = None,
        model_role: str = "default",
        temperature: float = 0.3,
        max_tool_rounds: int = 5,
        max_tokens: int = 2048,
        on_event: Optional[Callable[[TraceEvent], None]] = None,
        supports_fallback: bool = False,
    ):
        self.name = name
        self.instructions = instructions
        self.tools = tools or []
        self.response_format = response_format
        self.model_role = model_role
        self.temperature = temperature
        self.max_tool_rounds = max_tool_rounds
        self.max_tokens = max_tokens
        self.on_event = on_event
        # Tier-3 deterministic fallback: when True, this agent can produce a
        # schema-shaped result with no model (on model error, or in force mode).
        self.supports_fallback = supports_fallback
        self._tool_executors: dict[str, Callable] = {}

    def register_tool_executor(self, tool_name: str, executor: Callable) -> None:
        self._tool_executors[tool_name] = executor

    def _extract_json_payload(self, content: str) -> Any:
        if not content:
            return None

        # Reasoning models (e.g. phi-4-reasoning, deepseek-r1) wrap their
        # chain-of-thought in <think>...</think> before the final answer.
        # Strip it so it never reaches the JSON parser.
        cleaned = re.sub(r"<think>[\s\S]*?</think>", "", content, flags=re.IGNORECASE).strip()

        candidates = [cleaned, content.strip()]
        match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", cleaned)
        if match:
            candidates.insert(0, match.group(1).strip())

        # Fall back to the first balanced {...} or [...] span in the text.
        for opener, closer in (("{", "}"), ("[", "]")):
            start = cleaned.find(opener)
            end = cleaned.rfind(closer)
            if 0 <= start < end:
                candidates.append(cleaned[start:end + 1])

        for candidate in candidates:
            try:
                return json.loads(candidate)
            except Exception:
                continue
        return None

    async def _evaluate_groundedness(self, content: str) -> Optional[dict[str, Any]]:
        if self.name not in {"curator", "readiness_critic"} or not content.strip():
            return None

        result = await evaluate_async(
            content,
            model_config=get_eval_model_config(),
        )
        return {
            "score": result.score,
            "passed": result.passed,
            "evaluator": result.evaluator,
            "citation_count": result.citation_count,
            "assertion_count": result.assertion_count,
        }

    def _emit_critic_objections(self, run_id: str, content: str) -> None:
        if self.name != "readiness_critic":
            return

        payload = self._extract_json_payload(content)
        if isinstance(payload, dict):
            payload = payload.get("objections", [])
        if not isinstance(payload, list) or not payload:
            return

        objections = [item for item in payload if isinstance(item, dict)]
        if objections:
            self._emit(run_id, TraceEventType.CRITIC_OBJECTION, {"objections": objections})

    def _result_payload(self, result: Any) -> Any:
        if isinstance(result, BaseModel):
            return result.model_dump(mode="json")
        if isinstance(result, (dict, list, str, int, float, bool)) or result is None:
            return result
        return str(result)

    def _emit(self, run_id: str, event_type: TraceEventType, data: dict) -> None:
        if not self.on_event:
            return
        evt = TraceEvent(
            event_id=str(uuid.uuid4()),
            run_id=run_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            agent_name=self.name,
            data=data,
        )
        self.on_event(evt)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _model_call(self, client: AsyncOpenAI, **kwargs) -> Any:
        """Single model call with bounded retry on transient errors.

        Scoped to just the network call so a retry never re-executes tools
        or re-emits trace events for the whole agent run.
        """
        with span("model.call", agent=self.name, model=kwargs.get("model")):
            return await client.chat.completions.create(**kwargs)

    async def _create_completion(self, client: AsyncOpenAI, **kwargs) -> Any:
        """Cache-aware completion: SHA-256 cache hit skips the model call entirely.

        Only deterministic calls (temperature == 0) are cached — non-zero
        temperature is meant to vary, so caching it would be misleading.
        """
        from backend.core import llm_cache

        cacheable = float(kwargs.get("temperature", 0.0)) == 0.0
        key = None
        if cacheable:
            key = llm_cache.make_key(
                model=kwargs.get("model", ""),
                messages=kwargs.get("messages", []),
                tools=kwargs.get("tools"),
                temperature=kwargs.get("temperature", 0.0),
                max_tokens=kwargs.get("max_tokens", 0),
            )
            hit = llm_cache.get(key)
            if hit is not None:
                logger.debug("LLM cache hit for %s", self.name)
                return llm_cache.rehydrate_completion(hit)

        response = await self._model_call(client, **kwargs)
        if cacheable and key is not None:
            llm_cache.put(key, llm_cache.serialize_completion(response))
        return response

    async def run(
        self,
        messages: list[dict],
        run_id: str = "",
        context: Optional[dict] = None,
    ) -> AgentResult:
        """Tiered execution: model (with retry) → deterministic fallback.

        AGENT_FALLBACK_MODE controls behaviour:
          force → skip the model entirely (deterministic demo mode)
          auto  → fall back only when the model call fails (default)
          off   → never fall back; surface the error
        """
        run_id = run_id or str(uuid.uuid4())
        from config.settings import get_settings
        mode = get_settings().agent_fallback_mode

        if self.supports_fallback and mode == "force":
            return await self._run_fallback(run_id, context, reason="force mode")

        try:
            return await self._run_model(messages, run_id, context)
        except Exception as e:
            if not (self.supports_fallback and mode == "auto"):
                raise
            logger.warning("Agent '%s' → deterministic fallback (model error: %s)", self.name, e)
            return await self._run_fallback(run_id, context, reason=f"model error: {e}")

    async def _run_fallback(self, run_id: str, context: Optional[dict], reason: str) -> AgentResult:
        from backend.agents.fallbacks import build_fallback

        self._emit(run_id, TraceEventType.AGENT_START, {
            "model": "deterministic_fallback", "reason": reason[:200], "tools_available": [],
        })
        raw = await build_fallback(self.name, context)

        parsed = None
        if not isinstance(raw, str) and self.response_format is not None:
            try:
                parsed = self.response_format.model_validate(raw)
            except Exception as exc:
                logger.warning("Fallback output for %s failed schema validation: %s", self.name, exc)

        if isinstance(raw, str):
            content = raw
        elif parsed is not None:
            content = json.dumps(self._result_payload(parsed), indent=2)
        else:
            content = json.dumps(raw, indent=2, default=str)

        self._emit(run_id, TraceEventType.AGENT_COMPLETE, {
            "content": content,
            "structured_output": self._result_payload(parsed) if parsed is not None else raw,
            "content_length": len(content),
            "tool_calls_made": 0,
            "warnings": [],
            "fallback": True,
            "fallback_reason": reason[:200],
            "tokens": {"prompt": 0, "completion": 0},
        })
        return AgentResult(agent_name=self.name, content=content, parsed=parsed,
                           tool_calls_made=[], token_usage={"prompt": 0, "completion": 0})

    async def _run_model(
        self,
        messages: list[dict],
        run_id: str,
        context: Optional[dict] = None,
    ) -> AgentResult:
        ensure_model_loaded(self.model_role)
        client: AsyncOpenAI = get_client(self.model_role)
        model: str = get_model_name(self.model_role)

        system_msg = {"role": "system", "content": self.instructions}
        chat_messages = [system_msg] + messages
        tool_calls_made: list[dict] = []
        tool_results_payloads: list[Any] = []

        self._emit(run_id, TraceEventType.AGENT_START, {
            "model": model, "tools_available": [t["function"]["name"] for t in self.tools]
        })

        with agent_span(self.name, run_id=run_id, extra={"model": model, "role": self.model_role}):
            for _round in range(self.max_tool_rounds + 1):
                kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": chat_messages,
                    "temperature": self.temperature,
                    # Cap output length. Without this, some local models (e.g.
                    # qwen) can run away generating thousands of tokens for a
                    # structured response, stalling the workflow for minutes.
                    "max_tokens": self.max_tokens,
                }
                if self.tools:
                    kwargs["tools"] = self.tools
                    kwargs["tool_choice"] = "auto"

                response = await self._create_completion(client, **kwargs)
                msg = response.choices[0].message

                # No tool calls — final answer
                if not msg.tool_calls:
                    raw_content = msg.content or ""
                    content, warnings = apply_pipeline(raw_content, self.name)
                    groundedness = await self._evaluate_groundedness(content)
                    self._emit_critic_objections(run_id, content)

                    parsed = None

                    if self.response_format and content:
                        try:
                            parsed = self.response_format.model_validate_json(content)
                        except Exception:
                            try:
                                payload = self._extract_json_payload(content)
                                if isinstance(payload, (dict, list)):
                                    parsed = self.response_format.model_validate(payload)
                            except Exception as exc:
                                logger.warning("Could not parse structured output from %s: %s", self.name, exc)

                    if self.response_format and parsed is None:
                        for tool_result in reversed(tool_results_payloads):
                            try:
                                parsed = self.response_format.model_validate(tool_result)
                                break
                            except Exception:
                                continue

                    rendered_content = content
                    if parsed is not None:
                        rendered_content = json.dumps(self._result_payload(parsed), indent=2)

                    self._emit(run_id, TraceEventType.AGENT_COMPLETE, {
                        "content": rendered_content,
                        "structured_output": self._result_payload(parsed),
                        "content_length": len(rendered_content),
                        "tool_calls_made": len(tool_calls_made),
                        "warnings": warnings,
                        "groundedness": groundedness,
                        "tokens": {
                            "prompt": response.usage.prompt_tokens if response.usage else 0,
                            "completion": response.usage.completion_tokens if response.usage else 0,
                        }
                    })

                    return AgentResult(
                        agent_name=self.name,
                        content=rendered_content,
                        parsed=parsed,
                        tool_calls_made=tool_calls_made,
                        token_usage={
                            "prompt": response.usage.prompt_tokens if response.usage else 0,
                            "completion": response.usage.completion_tokens if response.usage else 0,
                        },
                    )

                # Execute tool calls
                chat_messages.append({"role": "assistant", "content": None, "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                    }
                    for tc in msg.tool_calls
                ]})

                for tc in msg.tool_calls:
                    fn_name = tc.function.name
                    fn_args = json.loads(tc.function.arguments or "{}")

                    self._emit(run_id, TraceEventType.TOOL_CALL, {
                        "tool": fn_name, "arguments": fn_args
                    })

                    executor = self._tool_executors.get(fn_name)
                    if executor:
                        try:
                            with span("tool.call", agent=self.name, tool=fn_name):
                                result = await executor(**fn_args)
                        except Exception as e:
                            result = {"error": str(e)}
                    else:
                        result = {"error": f"No executor registered for tool '{fn_name}'"}

                    tool_calls_made.append({"tool": fn_name, "args": fn_args, "result_summary": str(result)[:200]})
                    tool_results_payloads.append(self._result_payload(result))
                    self._emit(run_id, TraceEventType.TOOL_RESULT, {
                        "tool": fn_name,
                        "result_length": len(str(result)),
                        "result": self._result_payload(result),
                    })

                    chat_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result) if not isinstance(result, str) else result,
                    })

        # Model kept calling tools without finalising (some models are very
        # tool-eager). Rather than return a useless marker, fall back to the
        # deterministic builder so the stage still yields valid structured output.
        if self.supports_fallback:
            logger.warning("Agent '%s' hit max tool rounds → deterministic fallback", self.name)
            return await self._run_fallback(run_id, context, reason="max tool rounds reached")
        return AgentResult(agent_name=self.name, content="[max tool rounds reached]")
