"""
OpenTelemetry instrumentation.

Behaviour by config:
  ENABLE_TELEMETRY=false (default)
      Provider is installed but no exporter is attached.
      Spans are created and dropped — zero I/O overhead; all instrumentation
      code compiles and runs so Azure mode just works by flipping the flag.

  ENABLE_TELEMETRY=true + MODEL_BACKEND=foundry_local
      Console exporter at DEBUG level — good for tracing a single workflow run.

  ENABLE_TELEMETRY=true + MODEL_BACKEND=azure_foundry
      + APPLICATIONINSIGHTS_CONNECTION_STRING set
      Azure Monitor exporter → Application Insights.
      Falls back to console if the package is missing.

Usage:
    from backend.core.telemetry import setup_telemetry, agent_span

    # Once in FastAPI lifespan:
    setup_telemetry()

    # Around any async block:
    with agent_span("curator", run_id="abc", cert="AZ-204"):
        result = await agent.run(...)
"""
from __future__ import annotations

import logging
import random
from contextlib import contextmanager
from typing import Generator, Optional

logger = logging.getLogger(__name__)

_tracer = None


def _run_id_to_trace_id(run_id: str) -> Optional[int]:
    """A run_id is a UUID (128 bits) = a valid W3C trace-id. Strip dashes and
    parse as a 128-bit int so the App Insights operation_Id equals the UI run_id.
    Returns None if run_id isn't a 32-hex-char UUID."""
    hex_id = (run_id or "").replace("-", "")
    if len(hex_id) != 32:
        return None
    try:
        value = int(hex_id, 16)
        return value if value != 0 else None
    except ValueError:
        return None


def setup_telemetry() -> None:
    global _tracer
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry.sdk.trace import TracerProvider

        resource = Resource.create({SERVICE_NAME: "enterprisecertiq"})
        provider = TracerProvider(resource=resource)

        _attach_exporter(provider)

        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer("enterprisecertiq", "1.2.0")
        logger.info("Telemetry: OpenTelemetry ready")
    except ImportError:
        logger.warning("Telemetry: opentelemetry packages not installed; spans disabled")
    except Exception as e:
        logger.warning("Telemetry: setup error: %s", e)


def _attach_exporter(provider) -> None:
    from config.settings import get_settings
    s = get_settings()

    if not s.enable_telemetry:
        logger.debug("Telemetry: no exporter (ENABLE_TELEMETRY=false)")
        return

    conn_str = s.applicationinsights_connection_string
    if conn_str:
        try:
            from azure.monitor.opentelemetry.exporter import (
                AzureMonitorTraceExporter,
                AzureMonitorLogExporter,
            )
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
            from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
            from opentelemetry._logs import set_logger_provider
            from opentelemetry.sdk.resources import Resource, SERVICE_NAME
            import logging as _logging

            # Trace exporter — spans (workflow, agent, model, tool calls)
            provider.add_span_processor(
                BatchSpanProcessor(AzureMonitorTraceExporter(connection_string=conn_str))
            )

            # Log exporter — Python logger.warning/error → App Insights "traces"
            resource = Resource.create({SERVICE_NAME: "enterprisecertiq"})
            log_provider = LoggerProvider(resource=resource)
            log_provider.add_log_record_processor(
                BatchLogRecordProcessor(AzureMonitorLogExporter(connection_string=conn_str))
            )
            set_logger_provider(log_provider)

            # Bridge Python logging (WARNING+) → OTel log provider → App Insights
            log_handler = LoggingHandler(logger_provider=log_provider)
            log_handler.setLevel(_logging.WARNING)
            _logging.getLogger("backend").addHandler(log_handler)
            _logging.getLogger("config").addHandler(log_handler)

            logger.info(
                "Telemetry: Azure Monitor exporter enabled "
                "(traces=spans, logs=WARNING+ from backend.*)"
            )
            return
        except ImportError:
            logger.warning(
                "Telemetry: azure-monitor-opentelemetry-exporter not installed, "
                "falling back to console exporter"
            )

    # Console exporter (local debug or fallback when no App Insights conn string)
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
    provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    logger.info("Telemetry: console exporter enabled (ENABLE_TELEMETRY=true)")


def get_tracer():
    return _tracer


@contextmanager
def agent_span(
    agent_name: str,
    run_id: str = "",
    cert: str = "",
    extra: Optional[dict] = None,
) -> Generator:
    """
    Context manager that wraps a block in an OTel span named 'agent.<name>'.
    No-ops cleanly when telemetry is disabled — safe to use unconditionally.
    """
    tracer = _tracer
    if tracer is None:
        yield None
        return
    with tracer.start_as_current_span(f"agent.{agent_name}") as s:
        if run_id:
            s.set_attribute("run_id", run_id)
        if cert:
            s.set_attribute("cert_id", cert)
        if extra:
            for k, v in extra.items():
                s.set_attribute(k, str(v))
        yield s


@contextmanager
def workflow_span(run_id: str, learner_id: str, cert: str) -> Generator:
    """Top-level workflow span — wraps the entire agent pipeline.

    Roots the trace at the UI run_id so App Insights operation_Id == run_id
    (dashes stripped). All child agent/model/tool spans inherit this trace-id,
    so judges can paste the Live Journey Trace id straight into Transaction Search.
    """
    tracer = _tracer
    if tracer is None:
        yield None
        return

    parent_context = None
    trace_id = _run_id_to_trace_id(run_id)
    if trace_id is not None:
        try:
            from opentelemetry.trace import (
                SpanContext, TraceFlags, NonRecordingSpan, set_span_in_context,
            )
            seeded = SpanContext(
                trace_id=trace_id,
                span_id=random.getrandbits(64),
                is_remote=True,
                trace_flags=TraceFlags(TraceFlags.SAMPLED),
            )
            parent_context = set_span_in_context(NonRecordingSpan(seeded))
        except Exception as e:  # pragma: no cover - never block on telemetry
            logger.debug("Telemetry: could not seed trace-id from run_id: %s", e)
            parent_context = None

    with tracer.start_as_current_span("workflow.run", context=parent_context) as s:
        s.set_attribute("run_id", run_id)
        s.set_attribute("learner_id", learner_id)
        s.set_attribute("cert_id", cert)
        yield s


@contextmanager
def span(name: str, **attrs) -> Generator:
    """Generic child span (e.g. model call, tool call) → App Insights dependency."""
    tracer = _tracer
    if tracer is None:
        yield None
        return
    with tracer.start_as_current_span(name) as s:
        for k, v in attrs.items():
            if v is not None:
                s.set_attribute(k, str(v))
        yield s


def instrument_foundry_agents() -> None:
    """Enable GenAI/agent tracing so runs appear in the Foundry project's Tracing tab.

    Azure mode only. Sets AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING and instruments the
    agents SDK (AIAgentsInstrumentor — this SDK version's equivalent of
    AIProjectInstrumentor). Requires App Insights to be connected to the project in the
    portal (Agents → Traces → Connect) — see docs/foundry-hosted-agents.md.
    """
    import os
    try:
        from config.settings import get_settings, ModelBackend
        s = get_settings()
        if s.model_backend != ModelBackend.AZURE_FOUNDRY or not s.azure_ai_project_endpoint:
            return
        os.environ.setdefault("AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING", "true")
        # Path A (v2): AIProjectInstrumentor; Path B fallback (v1): AIAgentsInstrumentor.
        try:
            from azure.ai.projects.telemetry import AIProjectInstrumentor
            AIProjectInstrumentor().instrument()
            logger.info("Telemetry: Foundry GenAI instrumentation enabled (AIProjectInstrumentor / v2)")
            return
        except Exception:
            from azure.ai.agents.telemetry import AIAgentsInstrumentor
            AIAgentsInstrumentor().instrument()
            logger.info("Telemetry: Foundry GenAI instrumentation enabled (AIAgentsInstrumentor / v1)")
    except Exception as e:
        logger.warning("Telemetry: Foundry agent instrumentation skipped: %s", e)


def instrument_fastapi(app) -> None:
    """Auto-instrument FastAPI so every HTTP call is a tracked request in App Insights.
    No-op when telemetry is disabled or the package is missing."""
    if _tracer is None:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        logger.info("Telemetry: FastAPI instrumented (per-call request spans)")
    except Exception as e:
        logger.warning("Telemetry: FastAPI instrumentation skipped: %s", e)


def shutdown_telemetry() -> None:
    """Flush buffered spans on shutdown so nothing is lost (BatchSpanProcessor)."""
    try:
        from opentelemetry import trace
        provider = trace.get_tracer_provider()
        if hasattr(provider, "force_flush"):
            provider.force_flush()
        if hasattr(provider, "shutdown"):
            provider.shutdown()
    except Exception as e:  # pragma: no cover
        logger.debug("Telemetry shutdown flush skipped: %s", e)
