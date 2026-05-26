"""
Event Producer

Generates and publishes streaming events (transactions + clickstream)
to a Kafka topic via a Producer abstraction. The default
InMemoryProducer keeps the system runnable without a Kafka broker; pass
`KafkaProducer` from the confluent_kafka library to send to a real
cluster.

The producer supports an idempotent send mode (deduplicate by event_id)
that the consumer relies on for exactly-once semantics.
"""

from __future__ import annotations

import json
import logging
import random
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable, Dict, Iterator, List, Optional, Protocol


logger = logging.getLogger(__name__)


class EventType(str, Enum):
    TRANSACTION = "transaction"
    CLICK = "click"
    PAGE_VIEW = "page_view"
    LOGIN = "login"


@dataclass(frozen=True)
class Event:
    """One streaming event."""

    event_id: str  # idempotency key
    event_type: EventType
    user_id: str
    timestamp: datetime
    payload: Dict[str, object]

    def to_dict(self) -> Dict[str, object]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "payload": dict(self.payload),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class StreamSink(Protocol):
    """Pluggable sink: Kafka in production, in-memory for tests."""

    def publish(self, topic: str, key: str, value: bytes) -> None: ...

    def flush(self, timeout_seconds: float = 5.0) -> None: ...


class InMemoryProducer:
    """Reference sink for tests + CLI demos."""

    def __init__(self) -> None:
        self.records: Dict[str, List[Dict[str, object]]] = {}

    def publish(self, topic: str, key: str, value: bytes) -> None:
        self.records.setdefault(topic, []).append({"key": key, "value": value})

    def flush(self, timeout_seconds: float = 5.0) -> None:
        return None

    def messages(self, topic: str) -> List[Dict[str, object]]:
        return list(self.records.get(topic, []))


class EventProducer:
    """Publishes events to a configured StreamSink, deduplicating by event_id."""

    def __init__(
        self,
        sink: StreamSink,
        topic: str,
        *,
        idempotent: bool = True,
    ):
        self.sink = sink
        self.topic = topic
        self.idempotent = idempotent
        self._seen_ids: set[str] = set()
        self.sent_count = 0
        self.duplicate_count = 0

    def send(self, event: Event) -> bool:
        if self.idempotent and event.event_id in self._seen_ids:
            self.duplicate_count += 1
            return False
        self.sink.publish(
            topic=self.topic,
            key=event.user_id,
            value=event.to_json().encode("utf-8"),
        )
        if self.idempotent:
            self._seen_ids.add(event.event_id)
        self.sent_count += 1
        return True

    def send_batch(self, events: List[Event]) -> int:
        return sum(1 for e in events if self.send(e))

    def flush(self) -> None:
        self.sink.flush()


# -- Sample event generators -------------------------------------------


def generate_transaction(
    user_id: Optional[str] = None,
    *,
    now: Optional[datetime] = None,
    rng: Optional[random.Random] = None,
) -> Event:
    rng = rng or random.Random()
    return Event(
        event_id=str(uuid.UUID(int=rng.getrandbits(128))),
        event_type=EventType.TRANSACTION,
        user_id=user_id or f"u{rng.randint(1, 10_000):05d}",
        timestamp=now or datetime.now(timezone.utc),
        payload={
            "amount_usd": round(rng.uniform(1.0, 500.0), 2),
            "merchant": rng.choice(["amzn", "wmt", "kr", "tgt", "cstco"]),
            "city": rng.choice(["NYC", "SF", "LA", "SEA", "CHI"]),
            "card_type": rng.choice(["visa", "mc", "amex"]),
            "is_card_present": rng.random() > 0.4,
        },
    )


def generate_click(
    user_id: Optional[str] = None,
    *,
    now: Optional[datetime] = None,
    rng: Optional[random.Random] = None,
) -> Event:
    rng = rng or random.Random()
    return Event(
        event_id=str(uuid.UUID(int=rng.getrandbits(128))),
        event_type=EventType.CLICK,
        user_id=user_id or f"u{rng.randint(1, 10_000):05d}",
        timestamp=now or datetime.now(timezone.utc),
        payload={
            "page": rng.choice(["home", "product", "checkout", "cart"]),
            "product_id": f"p{rng.randint(1, 5000):05d}",
            "session_id": f"s{rng.randint(1, 1000):04d}",
        },
    )


def event_stream(
    count: int,
    *,
    seed: int = 42,
    duplicate_rate: float = 0.0,
    out_of_order_rate: float = 0.0,
    base_time: Optional[datetime] = None,
) -> Iterator[Event]:
    """Synthetic generator with controllable dedup + out-of-order rates."""
    rng = random.Random(seed)
    base_time = base_time or datetime.now(timezone.utc)
    generated: List[Event] = []
    for i in range(count):
        ts = base_time + timedelta(milliseconds=i * 10)
        if rng.random() < 0.7:
            evt = generate_transaction(now=ts, rng=rng)
        else:
            evt = generate_click(now=ts, rng=rng)
        generated.append(evt)
        yield evt
        if generated and rng.random() < duplicate_rate:
            # Re-emit a recently-seen event.
            yield rng.choice(generated[-10:])
        if generated and rng.random() < out_of_order_rate and len(generated) >= 5:
            # Re-emit an older event after a delay.
            yield rng.choice(generated[-5:])
