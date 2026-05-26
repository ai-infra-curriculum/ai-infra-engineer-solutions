"""Tests for the streaming feature pipeline."""

from datetime import datetime, timedelta, timezone
from typing import List

import pytest

from src.consumer import EventConsumer, InMemorySource
from src.processor import (
    FeatureBackfill,
    FeatureProcessor,
    FeatureRecord,
    FeatureStore,
    detect_skew,
)
from src.producer import (
    Event,
    EventProducer,
    EventType,
    InMemoryProducer,
    event_stream,
    generate_transaction,
    generate_click,
)


def _txn(user_id: str, amount: float, *, when: datetime, merchant: str = "amzn", city: str = "NYC") -> Event:
    return Event(
        event_id=f"{user_id}-{when.isoformat()}-{amount}",
        event_type=EventType.TRANSACTION,
        user_id=user_id,
        timestamp=when,
        payload={"amount_usd": amount, "merchant": merchant, "city": city, "is_card_present": True},
    )


class TestEventProducer:
    def test_send_records_to_sink(self):
        sink = InMemoryProducer()
        producer = EventProducer(sink, topic="events")
        producer.send(generate_transaction())
        assert len(sink.messages("events")) == 1

    def test_idempotent_rejects_duplicates(self):
        sink = InMemoryProducer()
        producer = EventProducer(sink, topic="events", idempotent=True)
        event = generate_transaction()
        assert producer.send(event) is True
        assert producer.send(event) is False
        assert producer.sent_count == 1
        assert producer.duplicate_count == 1

    def test_non_idempotent_allows_duplicates(self):
        sink = InMemoryProducer()
        producer = EventProducer(sink, topic="events", idempotent=False)
        event = generate_transaction()
        assert producer.send(event)
        assert producer.send(event)
        assert producer.sent_count == 2

    def test_send_batch(self):
        sink = InMemoryProducer()
        producer = EventProducer(sink, topic="events")
        events = [generate_transaction() for _ in range(10)]
        assert producer.send_batch(events) == 10

    def test_event_stream_yields_dupes_and_out_of_order(self):
        events = list(event_stream(count=20, seed=1, duplicate_rate=0.5, out_of_order_rate=0.5))
        # Should yield at least the original 20 + extras due to duplication.
        assert len(events) > 20


class TestFeatureProcessor:
    def test_processes_transaction_and_emits_features(self):
        p = FeatureProcessor()
        base = datetime.now(timezone.utc)
        record = p.process(_txn("u1", 10.0, when=base))
        assert record is not None
        assert record.features["txn_count_5m"] == 1.0
        assert record.features["txn_avg_amount_5m"] == 10.0

    def test_aggregates_multiple_transactions(self):
        p = FeatureProcessor()
        base = datetime.now(timezone.utc)
        for i in range(5):
            p.process(_txn("u1", 10.0 * (i + 1), when=base + timedelta(seconds=i)))
        # Latest record reflects the 5 events.
        record = p.process(_txn("u1", 100.0, when=base + timedelta(seconds=5)))
        assert record.features["txn_count_5m"] == 6.0
        assert record.features["txn_total_amount_5m"] == 10 + 20 + 30 + 40 + 50 + 100

    def test_unique_counts(self):
        p = FeatureProcessor()
        base = datetime.now(timezone.utc)
        p.process(_txn("u1", 10.0, when=base, merchant="amzn", city="NYC"))
        p.process(_txn("u1", 10.0, when=base + timedelta(seconds=1), merchant="wmt", city="LA"))
        record = p.process(_txn("u1", 10.0, when=base + timedelta(seconds=2), merchant="amzn", city="NYC"))
        assert record.features["txn_unique_merchants_5m"] == 2.0
        assert record.features["txn_unique_cities_5m"] == 2.0

    def test_window_trims_old_events(self):
        p = FeatureProcessor(window_seconds=60)
        base = datetime.now(timezone.utc)
        p.process(_txn("u1", 10.0, when=base))
        p.process(_txn("u1", 20.0, when=base + timedelta(seconds=30)))
        record = p.process(_txn("u1", 30.0, when=base + timedelta(seconds=120)))
        # First two events should have aged out.
        assert record.features["txn_count_5m"] == 1.0

    def test_duplicate_event_id_skipped(self):
        p = FeatureProcessor()
        base = datetime.now(timezone.utc)
        event = _txn("u1", 10.0, when=base)
        p.process(event)
        result = p.process(event)
        assert result is None
        assert p.stats.skipped_duplicate == 1

    def test_late_event_dropped(self):
        p = FeatureProcessor(window_seconds=60, allowed_lateness_seconds=30)
        base = datetime.now(timezone.utc)
        p.process(_txn("u1", 10.0, when=base + timedelta(minutes=10)))
        # Now send an event 30 minutes in the past — far past allowed_lateness.
        late_event = _txn("u2", 5.0, when=base - timedelta(minutes=30))
        # Need a unique event_id since the helper builds one from time.
        result = p.process(late_event)
        assert result is None
        assert p.stats.skipped_late == 1

    def test_watermark_advances_monotonically(self):
        p = FeatureProcessor()
        base = datetime.now(timezone.utc)
        p.process(_txn("u1", 10.0, when=base))
        assert p.watermark.timestamp == base
        p.process(_txn("u2", 10.0, when=base + timedelta(seconds=10)))
        assert p.watermark.timestamp == base + timedelta(seconds=10)

    def test_flush_emits_per_user(self):
        p = FeatureProcessor()
        base = datetime.now(timezone.utc)
        p.process(_txn("u1", 10.0, when=base))
        p.process(_txn("u2", 20.0, when=base))
        records = p.flush()
        assert {r.user_id for r in records} == {"u1", "u2"}


class TestFeatureStore:
    def test_write_and_read(self):
        store = FeatureStore()
        p = FeatureProcessor()
        base = datetime.now(timezone.utc)
        record = p.process(_txn("u1", 10.0, when=base))
        store.write(record)
        assert store.read("u1") == record
        assert len(store) == 1

    def test_overwrite_keeps_latest(self):
        store = FeatureStore()
        p = FeatureProcessor()
        base = datetime.now(timezone.utc)
        p.process(_txn("u1", 10.0, when=base))
        p.process(_txn("u1", 20.0, when=base + timedelta(seconds=10)))
        record = p.process(_txn("u1", 30.0, when=base + timedelta(seconds=20)))
        store.write(record)
        assert store.read("u1").features["txn_count_5m"] == 3.0


class TestConsumer:
    def test_consume_decodes_and_writes(self):
        sink = InMemoryProducer()
        producer = EventProducer(sink, topic="events")
        for _ in range(5):
            producer.send(generate_transaction(user_id="u1"))
        store = FeatureStore()
        processor = FeatureProcessor()
        source = InMemorySource(sink, topic="events")
        consumer = EventConsumer(source, processor, store)
        records = consumer.consume_once()
        assert len(records) == 5
        assert store.read("u1") is not None

    def test_consume_until_drained_handles_multiple_batches(self):
        sink = InMemoryProducer()
        producer = EventProducer(sink, topic="events")
        for _ in range(2500):
            producer.send(generate_transaction(user_id="u1"))
        store = FeatureStore()
        processor = FeatureProcessor()
        source = InMemorySource(sink, topic="events")
        consumer = EventConsumer(source, processor, store)
        records = consumer.consume_until_drained()
        assert len(records) == 2500

    def test_consumer_handles_bad_payloads(self):
        sink = InMemoryProducer()
        sink.publish("events", "u1", b"not-json")
        store = FeatureStore()
        processor = FeatureProcessor()
        source = InMemorySource(sink, topic="events")
        consumer = EventConsumer(source, processor, store)
        consumer.consume_once()
        assert consumer.stats.decode_errors == 1
        assert consumer.stats.written_features == 0


class TestExactlyOnce:
    def test_duplicate_events_dropped_end_to_end(self):
        sink = InMemoryProducer()
        producer = EventProducer(sink, topic="events", idempotent=False)
        event = generate_transaction(user_id="u1")
        producer.send(event)
        producer.send(event)  # duplicate
        producer.send(event)  # duplicate
        store = FeatureStore()
        processor = FeatureProcessor()
        source = InMemorySource(sink, topic="events")
        consumer = EventConsumer(source, processor, store)
        consumer.consume_until_drained()
        # Even though the sink has 3 copies, only one was processed.
        assert processor.stats.skipped_duplicate == 2
        record = store.read("u1")
        assert record.features["txn_count_5m"] == 1.0


class TestBackfill:
    def test_replay_matches_streaming_features(self):
        # Generate the same event sequence and feed it both online + backfill.
        events: List[Event] = []
        base = datetime.now(timezone.utc)
        for i in range(20):
            events.append(_txn("u1", 10.0 + i, when=base + timedelta(seconds=i)))

        # Online path.
        online = FeatureProcessor()
        for e in events:
            online.process(e)
        online_features = online.flush()[0]

        # Backfill path.
        offline = FeatureProcessor()
        backfill = FeatureBackfill(offline)
        backfill_records = backfill.backfill(events)
        offline_features = backfill_records[-1]

        # No skew between online and offline for the same input.
        differences = detect_skew(online_features, offline_features)
        assert not differences


class TestSkewDetection:
    def test_no_differences_under_tolerance(self):
        base = datetime.now(timezone.utc)
        a = FeatureRecord(user_id="u1", window_end=base,
                          features={"txn_count_5m": 10.0}, event_count=10, window_size_seconds=300)
        b = FeatureRecord(user_id="u1", window_end=base,
                          features={"txn_count_5m": 10.005}, event_count=10, window_size_seconds=300)
        assert detect_skew(a, b, tolerance=0.01) == {}

    def test_differences_reported(self):
        base = datetime.now(timezone.utc)
        a = FeatureRecord(user_id="u1", window_end=base,
                          features={"txn_count_5m": 10.0}, event_count=10, window_size_seconds=300)
        b = FeatureRecord(user_id="u1", window_end=base,
                          features={"txn_count_5m": 12.0}, event_count=12, window_size_seconds=300)
        skew = detect_skew(a, b)
        assert "txn_count_5m" in skew
        assert skew["txn_count_5m"] == (10.0, 12.0)
