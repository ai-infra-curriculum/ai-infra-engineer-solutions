"""
Distributed Tracer

Lightweight in-process tracer compatible with W3C Trace Context. Each
Span carries a trace_id + span_id, parent linkage, timing, status, and
key/value attributes. The Tracer accepts a TraceExporter Protocol so
callers can wire in Jaeger, Zipkin, Tempo, or OTLP without coupling
the rest of the system to a specific SDK.

A NoopExporter and an InMemoryExporter (for tests) ship with this
module.
"""

from __future__ import annotations

import contextvars
import logging
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Protocol


logger = logging.getLogger(__name__)


class SpanStatus(str, Enum):
    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


class SpanKind(str, Enum):
    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


@dataclass
class Span:
    """One unit of work in a trace."""

    name: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    service: str
    kind: SpanKind
    start_ns: int
    end_ns: Optional[int] = None
    status: SpanStatus = SpanStatus.UNSET
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        if self.end_ns is None:
            return 0.0
        return (self.end_ns - self.start_ns) / 1_000_000

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, **fields: Any) -> None:
        self.events.append({"name": name, "timestamp_ns": time.time_ns(), **fields})

    def record_exception(self, exc: BaseException) -> None:
        self.status = SpanStatus.ERROR
        self.attributes["exception.type"] = type(exc).__name__
        self.attributes["exception.message"] = str(exc)


class TraceExporter(Protocol):
    """Pluggable exporter for finished spans."""

    def export(self, spans: Iterable[Span]) -> None: ...


class NoopExporter:
    def export(self, spans: Iterable[Span]) -> None:
        return None


class InMemoryExporter:
    """Captures spans in memory; used by tests + the CLI demo."""

    def __init__(self) -> None:
        self.spans: List[Span] = []

    def export(self, spans: Iterable[Span]) -> None:
        self.spans.extend(spans)

    def trees(self) -> List["TraceTree"]:
        """Group spans by trace_id and return nested TraceTree records."""
        by_trace: Dict[str, List[Span]] = {}
        for span in self.spans:
            by_trace.setdefault(span.trace_id, []).append(span)
        return [build_trace_tree(spans) for spans in by_trace.values()]


@dataclass
class TraceTree:
    """A trace's spans assembled into a parent/child tree."""

    root: Span
    children: Dict[str, List["TraceTree"]]

    def total_duration_ms(self) -> float:
        return self.root.duration_ms

    def services(self) -> List[str]:
        seen = {self.root.service}
        for kids in self.children.values():
            for child in kids:
                seen.update(child.services())
        return sorted(seen)

    def flatten(self) -> List[Span]:
        out = [self.root]
        for kids in self.children.values():
            for child in kids:
                out.extend(child.flatten())
        return out


def build_trace_tree(spans: List[Span]) -> TraceTree:
    by_id = {s.span_id: s for s in spans}
    children_by_parent: Dict[str, List[Span]] = {}
    root: Optional[Span] = None
    for s in spans:
        if s.parent_span_id is None or s.parent_span_id not in by_id:
            root = s if root is None else min(root, s, key=lambda x: x.start_ns)
        else:
            children_by_parent.setdefault(s.parent_span_id, []).append(s)
    if root is None:
        # Pathological case: spans without a clear root; pick earliest.
        root = min(spans, key=lambda x: x.start_ns)

    def assemble(span: Span) -> TraceTree:
        kids: Dict[str, List[TraceTree]] = {}
        for child in children_by_parent.get(span.span_id, []):
            kids.setdefault(child.service, []).append(assemble(child))
        return TraceTree(root=span, children=kids)

    return assemble(root)


# -- Tracer + context propagation ---------------------------------------


# Holds the active span for the current task/thread.
_current_span: contextvars.ContextVar[Optional[Span]] = contextvars.ContextVar(
    "current_span", default=None,
)


class Tracer:
    """Lightweight tracer with W3C-style trace IDs."""

    def __init__(
        self,
        service: str,
        *,
        exporter: TraceExporter,
        clock: Callable[[], int] = time.time_ns,
        sampler: Callable[[str], bool] = lambda trace_id: True,
    ):
        self.service = service
        self.exporter = exporter
        self.clock = clock
        self.sampler = sampler
        self._buffer: List[Span] = []

    # -- public API ----------------------------------------------------

    def start_span(
        self,
        name: str,
        *,
        kind: SpanKind = SpanKind.INTERNAL,
        parent: Optional[Span] = None,
        attributes: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> Span:
        active = parent or _current_span.get()
        span = Span(
            name=name,
            trace_id=trace_id or (active.trace_id if active else self._new_trace_id()),
            span_id=self._new_span_id(),
            parent_span_id=active.span_id if active else None,
            service=self.service,
            kind=kind,
            start_ns=self.clock(),
            attributes=dict(attributes or {}),
        )
        return span

    def end_span(self, span: Span, *, status: Optional[SpanStatus] = None) -> None:
        span.end_ns = self.clock()
        if status is not None:
            span.status = status
        elif span.status is SpanStatus.UNSET:
            span.status = SpanStatus.OK
        if self.sampler(span.trace_id):
            self._buffer.append(span)

    def flush(self) -> None:
        if self._buffer:
            self.exporter.export(self._buffer)
            self._buffer.clear()

    # -- context-manager helper ---------------------------------------

    def in_span(
        self,
        name: str,
        *,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> "_SpanContext":
        return _SpanContext(tracer=self, name=name, kind=kind, attributes=attributes)

    # -- W3C trace-context propagation --------------------------------

    @staticmethod
    def inject(span: Span, headers: Dict[str, str]) -> None:
        """Inject the active span into outgoing request headers."""
        headers["traceparent"] = (
            f"00-{span.trace_id}-{span.span_id}-01"
        )

    @staticmethod
    def extract(headers: Dict[str, str]) -> Optional["RemoteContext"]:
        raw = headers.get("traceparent")
        if not raw:
            return None
        parts = raw.split("-")
        if len(parts) != 4:
            return None
        _, trace_id, span_id, _flags = parts
        return RemoteContext(trace_id=trace_id, span_id=span_id)

    # -- helpers -------------------------------------------------------

    def _new_trace_id(self) -> str:
        return secrets.token_hex(16)

    def _new_span_id(self) -> str:
        return secrets.token_hex(8)


@dataclass(frozen=True)
class RemoteContext:
    """Extracted trace context from inbound request headers."""

    trace_id: str
    span_id: str


class _SpanContext:
    """Context manager that activates a span for the enclosed block."""

    def __init__(
        self,
        tracer: Tracer,
        *,
        name: str,
        kind: SpanKind,
        attributes: Optional[Dict[str, Any]],
    ):
        self.tracer = tracer
        self.name = name
        self.kind = kind
        self.attributes = attributes
        self._token: Optional[contextvars.Token] = None
        self.span: Optional[Span] = None

    def __enter__(self) -> Span:
        self.span = self.tracer.start_span(self.name, kind=self.kind, attributes=self.attributes)
        self._token = _current_span.set(self.span)
        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.span is None:
            return
        if exc_val is not None:
            self.span.record_exception(exc_val)
        self.tracer.end_span(self.span)
        if self._token is not None:
            _current_span.reset(self._token)
