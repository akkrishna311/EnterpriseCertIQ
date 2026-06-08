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
from contextlib import contextmanager
from typing import Generator, Optional

logger = logging.getLogger(__name__)

_tracer = None


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
        # No exporter — spans created and silently dropped
        logger.debug("Telemetry: no exporter (ENABLE_TELEMETRY=false)")
        return

    if s.applicationinsights_connection_string:
        try:
            from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            exporter = AzureMonitorTraceExporter(
                connection_string=s.applicationinsights_connection_string
            )
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info("Telemetry: Azure Monitor exporter enabled")
            return
        except ImportError:
            logger.warning(
                "Telemetry: azure-monitor-opentelemetry not installed, "
                "falling back to console exporter"
            )

    # Console exporter (local debug or fallback)
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
    """Top-level workflow span — wraps the entire 6-agent pipeline."""
    tracer = _tracer
    if tracer is None:
        yield None
        return
    with tracer.start_as_current_span("workflow.run") as s:
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
