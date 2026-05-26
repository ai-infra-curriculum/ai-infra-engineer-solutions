"""
Alerting

Routes MonitorReport outcomes to alert channels (Slack, PagerDuty, or
the in-memory test channel) honoring a per-channel cooldown and
severity-routing rules.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable, Dict, List, Optional, Protocol

from .drift_detector import DriftSeverity
from .monitor import MonitorReport, RetrainingReason


logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    """One alert emitted by the monitor."""

    title: str
    severity: AlertSeverity
    body: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "title": self.title,
            "severity": self.severity.value,
            "body": self.body,
            "timestamp": self.timestamp.isoformat(),
            "tags": dict(self.tags),
        }


class AlertChannel(Protocol):
    """Pluggable channel: Slack, PagerDuty, etc."""

    name: str

    def send(self, alert: Alert) -> None: ...


class InMemoryAlertChannel:
    """Reference channel: captures alerts for inspection."""

    def __init__(self, name: str):
        self.name = name
        self.alerts: List[Alert] = []

    def send(self, alert: Alert) -> None:
        self.alerts.append(alert)


@dataclass
class RoutingRule:
    """Route alerts at-or-above `min_severity` to the named channel."""

    min_severity: AlertSeverity
    channel: AlertChannel


class AlertRouter:
    """Routes alerts to channels with deduplication + cooldown."""

    SEVERITY_ORDER = {
        AlertSeverity.INFO: 0,
        AlertSeverity.WARNING: 1,
        AlertSeverity.CRITICAL: 2,
    }

    def __init__(
        self,
        rules: List[RoutingRule],
        *,
        cooldown: timedelta = timedelta(minutes=5),
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self.rules = rules
        self.cooldown = cooldown
        self._last_sent: Dict[str, datetime] = {}
        self._clock = clock

    def emit(self, alert: Alert) -> List[str]:
        key = f"{alert.severity.value}::{alert.title}"
        now = self._clock()
        last = self._last_sent.get(key)
        if last is not None and (now - last) < self.cooldown:
            return []
        sent_channels: List[str] = []
        threshold = self.SEVERITY_ORDER[alert.severity]
        for rule in self.rules:
            if self.SEVERITY_ORDER[rule.min_severity] > threshold:
                continue
            rule.channel.send(alert)
            sent_channels.append(rule.channel.name)
        if sent_channels:
            self._last_sent[key] = now
        return sent_channels


def alerts_from_report(report: MonitorReport) -> List[Alert]:
    """Build one or more alerts from a MonitorReport."""
    alerts: List[Alert] = []

    # Performance alert.
    if report.performance.sample_count > 0 and report.performance.accuracy < 0.85:
        severity = (
            AlertSeverity.CRITICAL if report.performance.accuracy < 0.75
            else AlertSeverity.WARNING
        )
        alerts.append(Alert(
            title="Model accuracy below floor",
            severity=severity,
            body=(
                f"Live accuracy = {report.performance.accuracy:.4f} "
                f"(samples={report.performance.sample_count})"
            ),
            tags={"reason": report.retraining_reason.value},
        ))

    # Data drift alert.
    major = [r for r in report.drift_results if r.severity is DriftSeverity.MAJOR]
    moderate = [
        r for r in report.drift_results if r.severity is DriftSeverity.MODERATE
    ]
    if major:
        alerts.append(Alert(
            title="Major data drift detected",
            severity=AlertSeverity.CRITICAL,
            body="Major drift on: " + ", ".join(r.feature for r in major),
            tags={"features": ",".join(r.feature for r in major)},
        ))
    elif moderate:
        alerts.append(Alert(
            title="Moderate data drift detected",
            severity=AlertSeverity.WARNING,
            body="Moderate drift on: " + ", ".join(r.feature for r in moderate),
            tags={"features": ",".join(r.feature for r in moderate)},
        ))

    # Concept drift alert.
    if report.concept_drift and report.concept_drift.detected:
        cd = report.concept_drift
        severity = (
            AlertSeverity.CRITICAL if cd.severity is DriftSeverity.MAJOR
            else AlertSeverity.WARNING
        )
        alerts.append(Alert(
            title="Concept drift detected",
            severity=severity,
            body=(
                f"Reference accuracy {cd.reference_accuracy:.4f} → "
                f"live {cd.live_accuracy:.4f} (delta {cd.delta:.4f})"
            ),
            tags={"severity": cd.severity.value},
        ))

    # Retraining trigger alert (informational).
    if report.retraining_required:
        alerts.append(Alert(
            title="Retraining triggered",
            severity=AlertSeverity.INFO,
            body=(
                f"Retraining required: reason={report.retraining_reason.value}, "
                f"drifted_features={report.drifted_features}"
            ),
            tags={"reason": report.retraining_reason.value},
        ))

    return alerts
