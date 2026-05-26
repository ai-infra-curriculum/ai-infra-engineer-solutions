"""
Event Consumer

Reads events from a StreamSource, deserializes them, and feeds them
through a FeatureProcessor → FeatureStore pipeline. The consumer
guarantees exactly-once feature writes via the processor's idempotency
key (event_id) — duplicate events drop on the floor without producing
duplicate FeatureRecords.

The default InMemorySource pulls from the matching InMemoryProducer's
record list; pass `KafkaConsumer` from confluent_kafka for live
deployments.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Iterable, List, Optional, Protocol

from .processor import FeatureProcessor, FeatureRecord, FeatureStore
from .producer import Event, EventType, InMemoryProducer


logger = logging.getLogger(__name__)


class StreamSource(Protocol):
    """Pluggable source: in-memory for tests, Kafka in production."""

    def poll(self, *, max_messages: int = 1000, timeout_seconds: float = 1.0) -> List[bytes]: ...

    def commit(self) -> None: ...


class InMemorySource:
    """Source backed by an InMemoryProducer's record list."""

    def __init__(self, producer: InMemoryProducer, topic: str):
        self.producer = producer
        self.topic = topic
        self._offset = 0

    def poll(self, *, max_messages: int = 1000, timeout_seconds: float = 1.0) -> List[bytes]:
        records = self.producer.messages(self.topic)
        end = min(len(records), self._offset + max_messages)
        batch = records[self._offset:end]
        self._offset = end
        return [r["value"] for r in batch]

    def commit(self) -> None:
        return None


@dataclass
class ConsumerStats:
    polled: int = 0
    decoded: int = 0
    decode_errors: int = 0
    written_features: int = 0


def _decode_event(payload: bytes) -> Event:
    data = json.loads(payload.decode("utf-8"))
    return Event(
        event_id=data["event_id"],
        event_type=EventType(data["event_type"]),
        user_id=data["user_id"],
        timestamp=datetime.fromisoformat(data["timestamp"]),
        payload=dict(data.get("payload", {})),
    )


class EventConsumer:
    """Drives the source → processor → store pipeline."""

    def __init__(
        self,
        source: StreamSource,
        processor: FeatureProcessor,
        store: FeatureStore,
    ):
        self.source = source
        self.processor = processor
        self.store = store
        self.stats = ConsumerStats()

    def consume_once(self, *, max_messages: int = 1000) -> List[FeatureRecord]:
        """Pull up to N messages, process them, write to the store, return emitted records."""
        records: List[FeatureRecord] = []
        payloads = self.source.poll(max_messages=max_messages)
        self.stats.polled += len(payloads)
        for raw in payloads:
            try:
                event = _decode_event(raw)
            except Exception:
                self.stats.decode_errors += 1
                continue
            self.stats.decoded += 1
            output = self.processor.process(event)
            if output is not None:
                self.store.write(output)
                records.append(output)
                self.stats.written_features += 1
        self.source.commit()
        return records

    def consume_until_drained(self) -> List[FeatureRecord]:
        """Repeatedly poll until the source returns no records."""
        out: List[FeatureRecord] = []
        while True:
            batch = self.consume_once()
            if not batch:
                # Source returned nothing; we're caught up.
                break
            out.extend(batch)
        return out
