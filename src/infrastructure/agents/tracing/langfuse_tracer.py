#!/usr/bin/env python3
"""
LangfuseAgentTracer - Tracing et observabilité des agents Tawiza via Langfuse
Compatible avec Langfuse SDK v2.x et serveur Langfuse v2.x
"""

import asyncio
import functools
import os
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from loguru import logger

# Check if Langfuse is enabled via environment
_langfuse_enabled = os.getenv("LANGFUSE_ENABLED", "true").lower() == "true"

if _langfuse_enabled:
    try:
        from langfuse import Langfuse
        from langfuse.decorators import observe

        LANGFUSE_AVAILABLE = True
    except ImportError:
        LANGFUSE_AVAILABLE = False
        Langfuse = None
        observe = None
        logger.warning("Langfuse SDK not available. Install with: pip install 'langfuse<3.0'")
else:
    # Langfuse explicitly disabled via LANGFUSE_ENABLED=false
    LANGFUSE_AVAILABLE = False
    Langfuse = None
    observe = None
    logger.debug("Langfuse disabled via LANGFUSE_ENABLED=false")


@dataclass
class TraceMetadata:
    """Métadonnées d'une trace"""

    agent_name: str
    agent_type: str
    action: str
    input_data: dict[str, Any] | None = None
    output_data: dict[str, Any] | None = None
    duration_ms: float = 0.0
    success: bool = True
    error: str | None = None


class LangfuseAgentTracer:
    """Tracer Langfuse pour les agents Tawiza - Compatible SDK v2"""

    def __init__(
        self,
        public_key: str = None,
        secret_key: str = None,
        host: str = None,
        release: str = None,
        debug: bool = False,
    ):
        self.public_key = public_key or os.getenv("LANGFUSE_PUBLIC_KEY")
        self.secret_key = secret_key or os.getenv("LANGFUSE_SECRET_KEY")
        self.host = host or os.getenv("LANGFUSE_HOST", "http://localhost:3100")
        self.release = release or os.getenv("LANGFUSE_RELEASE", "tawiza-v2")
        self.debug = debug

        self.client: Langfuse | None = None
        self.is_initialized = False
        self.active_traces: dict[str, Any] = {}

    def initialize(self) -> bool:
        """Initialiser la connexion Langfuse"""
        if not LANGFUSE_AVAILABLE:
            logger.debug("Langfuse not available or disabled")
            return False

        # Double-check runtime env (in case module was imported before env was set)
        if os.getenv("LANGFUSE_ENABLED", "true").lower() != "true":
            logger.debug("Langfuse disabled via LANGFUSE_ENABLED=false")
            return False

        try:
            self.client = Langfuse(
                public_key=self.public_key,
                secret_key=self.secret_key,
                host=self.host,
                release=self.release,
                debug=self.debug,
            )

            self.is_initialized = True
            logger.info(f"🔍 Langfuse tracer initialized (host: {self.host})")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Langfuse: {e}")
            return False

    def ensure_initialized(self) -> bool:
        if not self.is_initialized:
            return self.initialize()
        return True

    # ==================== TRACE API ====================

    def start_trace(
        self,
        name: str,
        agent_name: str,
        agent_type: str,
        input_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> str | None:
        """Démarrer une nouvelle trace"""
        if not self.ensure_initialized():
            return None

        try:
            trace = self.client.trace(
                name=name,
                input=input_data,
                metadata={"agent_name": agent_name, "agent_type": agent_type, **(metadata or {})},
                tags=tags or [agent_type, agent_name],
            )

            trace_id = trace.id
            self.active_traces[trace_id] = {
                "trace": trace,
                "start_time": datetime.utcnow(),
                "spans": [],
            }

            logger.debug(f"Started trace {trace_id} for {agent_name}")
            return trace_id

        except Exception as e:
            logger.error(f"Failed to start trace: {e}")
            return None

    def end_trace(
        self,
        trace_id: str,
        output_data: dict[str, Any] | None = None,
        level: str = "DEFAULT",
        status_message: str | None = None,
    ) -> bool:
        """Terminer une trace"""
        if trace_id not in self.active_traces:
            return False

        try:
            trace_data = self.active_traces[trace_id]
            trace = trace_data["trace"]
            duration = (datetime.utcnow() - trace_data["start_time"]).total_seconds() * 1000

            trace.update(
                output=output_data,
                level=level,
                status_message=status_message,
                metadata={"duration_ms": duration},
            )

            del self.active_traces[trace_id]
            logger.debug(f"Ended trace {trace_id} ({duration:.1f}ms)")
            return True

        except Exception as e:
            logger.error(f"Failed to end trace: {e}")
            return False

    # ==================== SPAN API ====================

    def start_span(
        self,
        trace_id: str,
        name: str,
        input_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """Démarrer un span dans une trace"""
        if trace_id not in self.active_traces:
            return None

        try:
            trace = self.active_traces[trace_id]["trace"]
            span = trace.span(name=name, input=input_data, metadata=metadata)

            span_id = span.id
            self.active_traces[trace_id]["spans"].append(
                {"id": span_id, "span": span, "start_time": datetime.utcnow()}
            )

            return span_id

        except Exception as e:
            logger.error(f"Failed to start span: {e}")
            return None

    def end_span(
        self,
        trace_id: str,
        span_id: str,
        output_data: dict[str, Any] | None = None,
        level: str = "DEFAULT",
    ) -> bool:
        """Terminer un span"""
        if trace_id not in self.active_traces:
            return False

        try:
            spans = self.active_traces[trace_id]["spans"]
            span_data = next((s for s in spans if s["id"] == span_id), None)

            if span_data:
                span = span_data["span"]
                span.end(output=output_data, level=level)
                spans.remove(span_data)
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to end span: {e}")
            return False

    # ==================== GENERATION API ====================

    def log_generation(
        self,
        trace_id: str,
        name: str,
        model: str,
        input_data: Any,
        output_data: str,
        usage: dict[str, int] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Logger une génération LLM"""
        if trace_id not in self.active_traces:
            return False

        try:
            trace = self.active_traces[trace_id]["trace"]
            trace.generation(
                name=name,
                model=model,
                input=input_data,
                output=output_data,
                usage=usage,
                metadata=metadata,
            )
            return True

        except Exception as e:
            logger.error(f"Failed to log generation: {e}")
            return False

    # ==================== CONTEXT MANAGERS ====================

    @contextmanager
    def trace_context(
        self, name: str, agent_name: str, agent_type: str, input_data: dict[str, Any] | None = None
    ):
        """Context manager pour tracer une opération"""
        trace_id = self.start_trace(name, agent_name, agent_type, input_data)
        error = None

        try:
            yield trace_id
        except Exception as e:
            error = str(e)
            raise
        finally:
            level = "ERROR" if error else "DEFAULT"
            self.end_trace(trace_id, level=level, status_message=error)

    @asynccontextmanager
    async def async_trace_context(
        self, name: str, agent_name: str, agent_type: str, input_data: dict[str, Any] | None = None
    ):
        """Async context manager pour tracer une opération"""
        trace_id = self.start_trace(name, agent_name, agent_type, input_data)
        error = None

        try:
            yield trace_id
        except Exception as e:
            error = str(e)
            raise
        finally:
            level = "ERROR" if error else "DEFAULT"
            self.end_trace(trace_id, level=level, status_message=error)

    # ==================== DECORATOR ====================

    def trace_method(
        self, action_name: str = None, capture_input: bool = True, capture_output: bool = True
    ):
        """Décorateur pour tracer une méthode d'agent"""

        def decorator(func):
            @functools.wraps(func)
            async def async_wrapper(instance, *args, **kwargs):
                name = action_name or func.__name__
                agent_name = getattr(instance, "name", instance.__class__.__name__)
                agent_type = getattr(instance, "agent_type", "unknown")

                input_data = None
                if capture_input:
                    input_data = {"args": str(args)[:500], "kwargs": str(kwargs)[:500]}

                trace_id = self.start_trace(name, agent_name, agent_type, input_data)

                try:
                    result = await func(instance, *args, **kwargs)

                    output_data = None
                    if capture_output:
                        output_data = {"result": str(result)[:1000]}

                    self.end_trace(trace_id, output_data=output_data)
                    return result

                except Exception as e:
                    self.end_trace(trace_id, level="ERROR", status_message=str(e))
                    raise

            @functools.wraps(func)
            def sync_wrapper(instance, *args, **kwargs):
                name = action_name or func.__name__
                agent_name = getattr(instance, "name", instance.__class__.__name__)
                agent_type = getattr(instance, "agent_type", "unknown")

                input_data = None
                if capture_input:
                    input_data = {"args": str(args)[:500], "kwargs": str(kwargs)[:500]}

                trace_id = self.start_trace(name, agent_name, agent_type, input_data)

                try:
                    result = func(instance, *args, **kwargs)

                    output_data = None
                    if capture_output:
                        output_data = {"result": str(result)[:1000]}

                    self.end_trace(trace_id, output_data=output_data)
                    return result

                except Exception as e:
                    self.end_trace(trace_id, level="ERROR", status_message=str(e))
                    raise

            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper

        return decorator

    # ==================== SCORING ====================

    def score(self, trace_id: str, name: str, value: float, comment: str | None = None) -> bool:
        """Ajouter un score à une trace"""
        if not self.ensure_initialized():
            return False

        try:
            self.client.score(trace_id=trace_id, name=name, value=value, comment=comment)
            return True

        except Exception as e:
            logger.error(f"Failed to add score: {e}")
            return False

    # ==================== CLEANUP ====================

    def flush(self):
        """Envoyer toutes les traces en attente"""
        if self.client:
            try:
                self.client.flush()
                logger.debug("Langfuse traces flushed")
            except Exception as e:
                logger.error(f"Failed to flush traces: {e}")

    def shutdown(self):
        """Fermer proprement le client"""
        if self.client:
            try:
                self.flush()
                self.client.shutdown()
                logger.info("🔍 Langfuse tracer shutdown")
            except Exception as e:
                logger.error(f"Failed to shutdown Langfuse: {e}")


# ==================== SINGLETON & HELPERS ====================

_tracer: LangfuseAgentTracer | None = None


def get_tracer() -> LangfuseAgentTracer:
    """Obtenir l'instance singleton du tracer"""
    global _tracer
    if _tracer is None:
        _tracer = LangfuseAgentTracer()
        _tracer.initialize()
    return _tracer


def trace_agent_action(
    action_name: str = None, capture_input: bool = True, capture_output: bool = True
):
    """Décorateur global pour tracer une action d'agent"""
    return get_tracer().trace_method(action_name, capture_input, capture_output)


def trace_function(name: str = None):
    """Wrapper pour @observe si disponible"""
    if LANGFUSE_AVAILABLE and observe:
        return observe(name=name)

    def identity(func):
        return func

    return identity
