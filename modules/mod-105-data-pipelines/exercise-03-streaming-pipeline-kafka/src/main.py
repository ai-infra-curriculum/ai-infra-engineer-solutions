"""
Streaming Pipeline — CLI

Subcommands:
    demo        Run an end-to-end producer → consumer → store demo with
                synthetic events and print emitted features.
    backfill    Replay events through the processor in batch mode.
    inspect     Read one user's current feature record from the store.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import asdict
from typing import Optional

import click

from .consumer import (
    EventConsumer,
    InMemorySource,
)
from .processor import (
    FeatureBackfill,
    FeatureProcessor,
    FeatureStore,
)
from .producer import (
    EventProducer,
    InMemoryProducer,
    event_stream,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@click.group()
@click.option("--verbose", "-v", is_flag=True)
def cli(verbose: bool) -> None:
    """Streaming feature pipeline."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.option("--events", default=200, type=int)
@click.option("--duplicate-rate", default=0.1, type=float)
@click.option("--out-of-order-rate", default=0.05, type=float)
@click.option("--window-seconds", default=300, type=int)
@click.option("--seed", default=42, type=int)
def demo(events: int, duplicate_rate: float, out_of_order_rate: float, window_seconds: int, seed: int) -> None:
    """Run end-to-end producer → consumer → store demo."""
    sink = InMemoryProducer()
    producer = EventProducer(sink, topic="events")
    for event in event_stream(
        count=events,
        duplicate_rate=duplicate_rate,
        out_of_order_rate=out_of_order_rate,
        seed=seed,
    ):
        producer.send(event)
    producer.flush()

    store = FeatureStore()
    processor = FeatureProcessor(window_seconds=window_seconds)
    source = InMemorySource(sink, topic="events")
    consumer = EventConsumer(source, processor, store)
    consumer.consume_until_drained()

    click.echo(f"Producer sent: {producer.sent_count}, duplicates rejected: {producer.duplicate_count}")
    click.echo(f"Consumer polled {consumer.stats.polled}, decoded {consumer.stats.decoded}")
    click.echo(
        f"Processor processed {processor.stats.processed}, "
        f"skipped duplicate {processor.stats.skipped_duplicate}, "
        f"skipped late {processor.stats.skipped_late}"
    )
    click.echo(f"Feature store now has {len(store)} users with features.\n")
    # Show 5 sample records.
    for user_id in sorted(store.records.keys())[:5]:
        record = store.read(user_id)
        click.echo(f"  {user_id}: txn={record.features['txn_count_5m']:.0f} "
                   f"avg_amt={record.features['txn_avg_amount_5m']:.2f} "
                   f"unique_merchants={record.features['txn_unique_merchants_5m']:.0f}")


@cli.command()
@click.option("--events", default=200, type=int)
@click.option("--seed", default=42, type=int)
@click.option("--window-seconds", default=300, type=int)
def backfill(events: int, seed: int, window_seconds: int) -> None:
    """Backfill features by replaying events in offline-batch mode."""
    sink = InMemoryProducer()
    producer = EventProducer(sink, topic="events")
    all_events = list(event_stream(count=events, seed=seed))
    for event in all_events:
        producer.send(event)
    processor = FeatureProcessor(window_seconds=window_seconds)
    backfill = FeatureBackfill(processor)
    records = backfill.backfill(all_events)
    click.echo(f"Backfilled {len(records)} feature records from {len(all_events)} events")
    if records:
        click.echo("Last 3 records:")
        for r in records[-3:]:
            click.echo(
                f"  {r.user_id}: window_end={r.window_end.isoformat(timespec='seconds')} "
                f"events={r.event_count}"
            )


@cli.command()
@click.option("--events", default=200, type=int)
@click.option("--user", required=True)
@click.option("--seed", default=42, type=int)
def inspect(events: int, user: str, seed: int) -> None:
    """Run the demo and print one user's stored feature record."""
    sink = InMemoryProducer()
    producer = EventProducer(sink, topic="events")
    for event in event_stream(count=events, seed=seed):
        producer.send(event)
    store = FeatureStore()
    processor = FeatureProcessor()
    consumer = EventConsumer(InMemorySource(sink, topic="events"), processor, store)
    consumer.consume_until_drained()
    record = store.read(user)
    if record is None:
        click.echo(f"No features recorded for {user}.")
        sys.exit(1)
    click.echo(json.dumps({
        "user_id": record.user_id,
        "window_end": record.window_end.isoformat(),
        "event_count": record.event_count,
        "features": record.features,
    }, indent=2))


if __name__ == "__main__":
    cli()
