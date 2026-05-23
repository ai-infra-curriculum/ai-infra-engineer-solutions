"""Backfill driver: three strategies + safety rails."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable, Iterable

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill")


@dataclass(frozen=True)
class Unit:
    """One backfill unit: a date or a (date, shard) tuple."""
    day: date
    shard: str | None = None

    def key(self) -> str:
        return f"{self.day}/{self.shard}" if self.shard else f"{self.day}"


def date_range(start: date, end: date) -> Iterable[date]:
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def open_audit() -> sqlite3.Connection:
    conn = sqlite3.connect("backfill_audit.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit (
            ts TEXT, strategy TEXT, unit TEXT, status TEXT, duration_s REAL, error TEXT
        )
    """)
    return conn


def run_unit(unit: Unit) -> tuple[Unit, str, float, str | None]:
    """Simulated backfill operation. Replace with real workload."""
    t0 = time.perf_counter()
    try:
        time.sleep(0.05)              # pretend it does work
        return unit, "ok", time.perf_counter() - t0, None
    except Exception as e:
        return unit, "fail", time.perf_counter() - t0, str(e)


def sequential(units: list[Unit], audit: sqlite3.Connection):
    for u in units:
        unit, status, dur, err = run_unit(u)
        audit.execute("INSERT INTO audit VALUES(datetime('now'),?,?,?,?,?)",
                      ("sequential", unit.key(), status, dur, err))
        log.info(f"seq {unit.key()} {status} {dur:.3f}s")
    audit.commit()


def parallel_by_date(units: list[Unit], audit: sqlite3.Connection, concurrency: int):
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as ex:
        for unit, status, dur, err in ex.map(run_unit, units):
            audit.execute("INSERT INTO audit VALUES(datetime('now'),?,?,?,?,?)",
                          ("parallel_by_date", unit.key(), status, dur, err))
    audit.commit()


def parallel_by_shard(units: list[Unit], audit: sqlite3.Connection, concurrency: int):
    """Date-major, shard-minor: ensure parent day done before next day starts."""
    by_day: dict[date, list[Unit]] = {}
    for u in units:
        by_day.setdefault(u.day, []).append(u)

    for day, ushards in sorted(by_day.items()):
        log.info(f"day {day}: {len(ushards)} shards")
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as ex:
            for unit, status, dur, err in ex.map(run_unit, ushards):
                audit.execute("INSERT INTO audit VALUES(datetime('now'),?,?,?,?,?)",
                              ("parallel_by_shard", unit.key(), status, dur, err))
    audit.commit()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--strategy", choices=["sequential", "parallel-date", "parallel-shard"], required=True)
    p.add_argument("--start", type=date.fromisoformat, required=True)
    p.add_argument("--end", type=date.fromisoformat, required=True)
    p.add_argument("--shards", type=int, default=1, help="number of shards per day")
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--retry-failed", action="store_true")
    args = p.parse_args()

    units = [
        Unit(d, shard=f"s{i}" if args.shards > 1 else None)
        for d in date_range(args.start, args.end)
        for i in range(args.shards)
    ]

    if args.retry_failed:
        conn = open_audit()
        failed = {row[0] for row in conn.execute(
            "SELECT unit FROM audit WHERE status='fail'")}
        units = [u for u in units if u.key() in failed]
        log.info(f"retrying {len(units)} previously-failed units")

    if args.dry_run:
        plan = [{"unit": u.key()} for u in units]
        print(json.dumps({"strategy": args.strategy, "units": plan,
                          "estimated_seconds": len(plan) * 0.05}, indent=2))
        return

    audit = open_audit()
    t0 = time.perf_counter()
    if args.strategy == "sequential":
        sequential(units, audit)
    elif args.strategy == "parallel-date":
        parallel_by_date(units, audit, args.concurrency)
    else:
        parallel_by_shard(units, audit, args.concurrency)
    log.info(f"done in {time.perf_counter() - t0:.1f}s")


if __name__ == "__main__":
    main()
