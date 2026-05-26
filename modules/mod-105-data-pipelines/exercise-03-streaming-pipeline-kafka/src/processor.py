"""
Stream Processor — feature engineering on Event streams

Computes time-window aggregations + transformations + watermark-driven
late-data handling. The processor maintains per-user state and emits
FeatureRecords downstream as windows close. Designed to be a faithful
Python equivalent of the Flink/SQL feature definitions the curriculum
references; production deployments swap the in-process state for
Flink's keyed-state APIs.
"""

from __future__ import annotations

import logging
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Deque, Dict, Iterable, List, Optional, Tuple

from .producer import Event, EventType


logger = logging.getLogger(__name__)


@dataclass
class FeatureRecord:
    """One row of computed features for a user at a point in time."""

    user_id: str
    window_end: datetime
    features: Dict[str, float]
    event_count: int
    window_size_seconds: int


@dataclass
class Watermark:
    """Highest timestamp the processor has observed; bounds 'late'."""

    timestamp: datetime
    allowed_lateness: timedelta = field(default_factory=lambda: timedelta(seconds=30))

    def is_late(self, event_time: datetime) -> bool:
        return event_time + self.allowed_lateness < self.timestamp


@dataclass
class ProcessorStats:
    processed: int = 0
    skipped_duplicate: int = 0
    skipped_late: int = 0
    features_emitted: int = 0


class FeatureProcessor:
    """Per-user windowed feature computation."""

    def __init__(
        self,
        window_seconds: int = 300,  # 5-minute rolling window
        *,
        allowed_lateness_seconds: int = 30,
        idempotent: bool = True,
    ):
        self.window = timedelta(seconds=window_seconds)
        self.allowed_lateness = timedelta(seconds=allowed_lateness_seconds)
        self.idempotent = idempotent
        self._buffers: Dict[str, Deque[Event]] = defaultdict(deque)
        self._seen_ids: set[str] = set()
        self._watermark: Optional[Watermark] = None
        self.stats = ProcessorStats()

    @property
    def watermark(self) -> Optional[Watermark]:
        return self._watermark

    # -- streaming API -------------------------------------------------

    def process(self, event: Event) -> Optional[FeatureRecord]:
        """Ingest one event, return the latest FeatureRecord for that user."""
        if self.idempotent and event.event_id in self._seen_ids:
            self.stats.skipped_duplicate += 1
            return None

        self._advance_watermark(event)
        if self._watermark and self._watermark.is_late(event.timestamp):
            self.stats.skipped_late += 1
            return None

        self._seen_ids.add(event.event_id)
        buf = self._buffers[event.user_id]
        buf.append(event)
        self._trim_window(buf, now=event.timestamp)
        self.stats.processed += 1

        features = self._compute_features(event.user_id, buf)
        record = FeatureRecord(
            user_id=event.user_id,
            window_end=event.timestamp,
            features=features,
            event_count=len(buf),
            window_size_seconds=int(self.window.total_seconds()),
        )
        self.stats.features_emitted += 1
        return record

    def flush(self) -> List[FeatureRecord]:
        """Emit a final FeatureRecord per active user."""
        records: List[FeatureRecord] = []
        now = self._watermark.timestamp if self._watermark else datetime.now(timezone.utc)
        for user_id, buf in self._buffers.items():
            self._trim_window(buf, now=now)
            if not buf:
                continue
            records.append(FeatureRecord(
                user_id=user_id,
                window_end=now,
                features=self._compute_features(user_id, buf),
                event_count=len(buf),
                window_size_seconds=int(self.window.total_seconds()),
            ))
        return records

    # -- internals -----------------------------------------------------

    def _advance_watermark(self, event: Event) -> None:
        if self._watermark is None or event.timestamp > self._watermark.timestamp:
            self._watermark = Watermark(
                timestamp=event.timestamp,
                allowed_lateness=self.allowed_lateness,
            )

    def _trim_window(self, buf: Deque[Event], *, now: datetime) -> None:
        cutoff = now - self.window
        while buf and buf[0].timestamp < cutoff:
            buf.popleft()

    def _compute_features(self, user_id: str, buf: Iterable[Event]) -> Dict[str, float]:
        events = list(buf)
        txn_events = [e for e in events if e.event_type is EventType.TRANSACTION]
        click_events = [e for e in events if e.event_type is EventType.CLICK]

        amounts = [
            float(e.payload.get("amount_usd", 0.0))
            for e in txn_events
        ]
        unique_merchants = {
            str(e.payload.get("merchant", ""))
            for e in txn_events
            if e.payload.get("merchant")
        }
        unique_cities = {
            str(e.payload.get("city", ""))
            for e in txn_events
            if e.payload.get("city")
        }
        card_present_count = sum(
            1 for e in txn_events
            if e.payload.get("is_card_present", False)
        )

        if amounts:
            avg_amount = statistics.mean(amounts)
            max_amount = max(amounts)
            total_amount = sum(amounts)
            stdev_amount = statistics.pstdev(amounts) if len(amounts) > 1 else 0.0
        else:
            avg_amount = max_amount = total_amount = stdev_amount = 0.0

        return {
            "txn_count_5m": float(len(txn_events)),
            "txn_avg_amount_5m": round(avg_amount, 2),
            "txn_max_amount_5m": round(max_amount, 2),
            "txn_total_amount_5m": round(total_amount, 2),
            "txn_amount_stdev_5m": round(stdev_amount, 2),
            "txn_unique_merchants_5m": float(len(unique_merchants)),
            "txn_unique_cities_5m": float(len(unique_cities)),
            "txn_card_present_ratio_5m": round(
                card_present_count / max(1, len(txn_events)), 3,
            ),
            "click_count_5m": float(len(click_events)),
            "click_to_txn_ratio_5m": round(
                len(click_events) / max(1, len(txn_events)), 3,
            ),
        }


# -- Offline feature backfill ------------------------------------------


class FeatureBackfill:
    """Replays historical events through a fresh processor to materialize features."""

    def __init__(self, processor: FeatureProcessor):
        self.processor = processor

    def backfill(self, events: Iterable[Event]) -> List[FeatureRecord]:
        records: List[FeatureRecord] = []
        # Sort by timestamp for deterministic replay.
        for event in sorted(events, key=lambda e: e.timestamp):
            record = self.processor.process(event)
            if record is not None:
                records.append(record)
        records.extend(self.processor.flush())
        return records


# -- Feature store sink ------------------------------------------------


@dataclass
class FeatureStore:
    """In-memory online feature store keyed by user_id."""

    records: Dict[str, FeatureRecord] = field(default_factory=dict)

    def write(self, record: FeatureRecord) -> None:
        self.records[record.user_id] = record

    def write_many(self, records: Iterable[FeatureRecord]) -> int:
        count = 0
        for r in records:
            self.write(r)
            count += 1
        return count

    def read(self, user_id: str) -> Optional[FeatureRecord]:
        return self.records.get(user_id)

    def __len__(self) -> int:
        return len(self.records)


# -- Consistency check (training/serving skew) -------------------------


def detect_skew(
    online_record: FeatureRecord,
    offline_record: FeatureRecord,
    *,
    tolerance: float = 0.01,
) -> Dict[str, Tuple[float, float]]:
    """Returns features where online != offline by more than `tolerance`."""
    differences: Dict[str, Tuple[float, float]] = {}
    for key, online_value in online_record.features.items():
        offline_value = offline_record.features.get(key, 0.0)
        if abs(online_value - offline_value) > tolerance:
            differences[key] = (online_value, offline_value)
    return differences
