"""
Model Registry

MLflow-style model registry: each registered_model has an ordered list
of versions, and each version has a Stage (None / Staging / Production /
Archived). Promotions move a version through stages; the registry
enforces "only one Production version at a time per model" and
exposes lineage from a registry entry back to the experiment run that
produced it.

Auto-promotion is implemented as a PromotionPolicy that compares a
candidate run's metrics against the current Production version's
metrics and either promotes, rejects, or rolls back.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Dict, List, Optional

from .experiment_tracker import Run


logger = logging.getLogger(__name__)


class Stage(str, Enum):
    NONE = "None"
    STAGING = "Staging"
    PRODUCTION = "Production"
    ARCHIVED = "Archived"


@dataclass
class ModelVersion:
    """One version of a registered model."""

    model_name: str
    version: int
    stage: Stage
    artifact_uri: str
    run_id: str
    created_at: datetime
    metrics: Dict[str, float] = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "model_name": self.model_name,
            "version": self.version,
            "stage": self.stage.value,
            "artifact_uri": self.artifact_uri,
            "run_id": self.run_id,
            "created_at": self.created_at.isoformat(),
            "metrics": dict(self.metrics),
            "description": self.description,
        }


@dataclass
class RegisteredModel:
    """Logical model in the registry."""

    name: str
    versions: List[ModelVersion] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class StageTransition:
    """Audit record for a stage change."""

    model_name: str
    version: int
    from_stage: Stage
    to_stage: Stage
    actor: str
    reason: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RegistryError(Exception):
    """Raised when a registry operation violates invariants."""


# -- Registry -----------------------------------------------------------


class ModelRegistry:
    """In-memory model registry with stage transitions + audit log."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self._models: Dict[str, RegisteredModel] = {}
        self.transitions: List[StageTransition] = []
        self._clock = clock

    def register(
        self,
        *,
        model_name: str,
        artifact_uri: str,
        run_id: str,
        metrics: Optional[Dict[str, float]] = None,
        description: str = "",
    ) -> ModelVersion:
        model = self._models.setdefault(
            model_name,
            RegisteredModel(name=model_name, created_at=self._clock()),
        )
        next_version = len(model.versions) + 1
        record = ModelVersion(
            model_name=model_name,
            version=next_version,
            stage=Stage.NONE,
            artifact_uri=artifact_uri,
            run_id=run_id,
            created_at=self._clock(),
            metrics=dict(metrics or {}),
            description=description,
        )
        model.versions.append(record)
        return record

    def transition(
        self,
        model_name: str,
        version: int,
        target_stage: Stage,
        *,
        actor: str = "system",
        reason: str = "",
    ) -> ModelVersion:
        model = self._models.get(model_name)
        if model is None:
            raise RegistryError(f"Unknown model {model_name!r}")
        target_version = next(
            (v for v in model.versions if v.version == version), None,
        )
        if target_version is None:
            raise RegistryError(f"Unknown version {version} of {model_name!r}")
        # Archive the existing Production when promoting another version.
        if target_stage is Stage.PRODUCTION:
            for v in model.versions:
                if v.version != version and v.stage is Stage.PRODUCTION:
                    self.transitions.append(StageTransition(
                        model_name=model_name,
                        version=v.version,
                        from_stage=v.stage,
                        to_stage=Stage.ARCHIVED,
                        actor=actor,
                        reason=f"Archived in favor of v{version}",
                        timestamp=self._clock(),
                    ))
                    v.stage = Stage.ARCHIVED
        previous = target_version.stage
        target_version.stage = target_stage
        self.transitions.append(StageTransition(
            model_name=model_name,
            version=version,
            from_stage=previous,
            to_stage=target_stage,
            actor=actor,
            reason=reason,
            timestamp=self._clock(),
        ))
        return target_version

    def get(self, model_name: str, version: int) -> ModelVersion:
        model = self._models.get(model_name)
        if model is None:
            raise RegistryError(f"Unknown model {model_name!r}")
        for v in model.versions:
            if v.version == version:
                return v
        raise RegistryError(f"Unknown version {version} of {model_name!r}")

    def list_versions(self, model_name: str, *, stage: Optional[Stage] = None) -> List[ModelVersion]:
        model = self._models.get(model_name)
        if model is None:
            return []
        if stage is None:
            return list(model.versions)
        return [v for v in model.versions if v.stage is stage]

    def production_version(self, model_name: str) -> Optional[ModelVersion]:
        prod = self.list_versions(model_name, stage=Stage.PRODUCTION)
        if not prod:
            return None
        if len(prod) > 1:  # invariant violated; surface it
            raise RegistryError(
                f"Model {model_name!r} has multiple Production versions: "
                f"{[v.version for v in prod]}"
            )
        return prod[0]

    def rollback(self, model_name: str, *, actor: str = "system") -> ModelVersion:
        """Roll back to the most recent previously-Production (now Archived) version."""
        current = self.production_version(model_name)
        if current is None:
            raise RegistryError(f"No active Production version for {model_name!r}")
        model = self._models[model_name]
        # The candidate is the most recent ARCHIVED with a Production
        # transition that we can find from the audit log.
        previous = self._find_previous_production(model_name, current.version)
        if previous is None:
            raise RegistryError(
                f"No previous Production version available to roll back to."
            )
        # Move current to Archived, restore previous to Production.
        self.transition(model_name, current.version, Stage.ARCHIVED,
                        actor=actor, reason="Rollback")
        return self.transition(model_name, previous.version, Stage.PRODUCTION,
                               actor=actor, reason="Rollback to previous Production")

    def _find_previous_production(
        self,
        model_name: str,
        current_version: int,
    ) -> Optional[ModelVersion]:
        # Walk audit log backwards to find the most recent Production transition
        # before the current version.
        for entry in reversed(self.transitions):
            if (
                entry.model_name == model_name
                and entry.to_stage is Stage.PRODUCTION
                and entry.version != current_version
            ):
                return self.get(model_name, entry.version)
        return None

    def lineage(self, model_name: str, version: int) -> Dict[str, object]:
        """Return a lineage record (run_id + transitions)."""
        record = self.get(model_name, version)
        transitions = [
            {
                "from_stage": t.from_stage.value,
                "to_stage": t.to_stage.value,
                "actor": t.actor,
                "reason": t.reason,
                "timestamp": t.timestamp.isoformat(),
            }
            for t in self.transitions
            if t.model_name == model_name and t.version == version
        ]
        return {
            "model_name": model_name,
            "version": version,
            "run_id": record.run_id,
            "artifact_uri": record.artifact_uri,
            "metrics": dict(record.metrics),
            "current_stage": record.stage.value,
            "transitions": transitions,
        }


# -- Promotion policy ---------------------------------------------------


@dataclass(frozen=True)
class PromotionDecision:
    candidate: ModelVersion
    incumbent: Optional[ModelVersion]
    promote: bool
    reason: str
    metric_deltas: Dict[str, float] = field(default_factory=dict)


@dataclass
class PromotionPolicy:
    """Promote a candidate when it beats the incumbent by min_improvement."""

    metric: str  # e.g., "accuracy" or "f1"
    higher_is_better: bool = True
    min_improvement: float = 0.001
    require_min_value: Optional[float] = None
    forbid_regression_in: List[str] = field(default_factory=list)

    def decide(
        self,
        candidate: ModelVersion,
        incumbent: Optional[ModelVersion],
    ) -> PromotionDecision:
        if self.metric not in candidate.metrics:
            return PromotionDecision(
                candidate=candidate, incumbent=incumbent,
                promote=False,
                reason=f"Candidate is missing required metric {self.metric!r}",
            )
        candidate_value = candidate.metrics[self.metric]
        if self.require_min_value is not None:
            below = (
                candidate_value < self.require_min_value
                if self.higher_is_better
                else candidate_value > self.require_min_value
            )
            if below:
                return PromotionDecision(
                    candidate=candidate, incumbent=incumbent, promote=False,
                    reason=(
                        f"Candidate {self.metric}={candidate_value:.4f} fails "
                        f"require_min_value={self.require_min_value}"
                    ),
                )
        if incumbent is None:
            return PromotionDecision(
                candidate=candidate, incumbent=None, promote=True,
                reason="No incumbent Production version; promoting candidate.",
            )
        incumbent_value = incumbent.metrics.get(self.metric, 0.0)
        delta = candidate_value - incumbent_value
        improvement = delta if self.higher_is_better else -delta
        deltas = {self.metric: round(delta, 6)}
        # Guard against regressions on other tracked metrics.
        for key in self.forbid_regression_in:
            if key == self.metric:
                continue
            inc_v = incumbent.metrics.get(key)
            cand_v = candidate.metrics.get(key)
            if inc_v is None or cand_v is None:
                continue
            deltas[key] = round(cand_v - inc_v, 6)
            regressed = (
                cand_v < inc_v if self.higher_is_better else cand_v > inc_v
            )
            if regressed:
                return PromotionDecision(
                    candidate=candidate, incumbent=incumbent, promote=False,
                    reason=(
                        f"Candidate regresses on {key!r} "
                        f"({inc_v:.4f} → {cand_v:.4f})"
                    ),
                    metric_deltas=deltas,
                )
        if improvement < self.min_improvement:
            return PromotionDecision(
                candidate=candidate, incumbent=incumbent, promote=False,
                reason=(
                    f"Improvement {improvement:.4f} below threshold "
                    f"{self.min_improvement}"
                ),
                metric_deltas=deltas,
            )
        return PromotionDecision(
            candidate=candidate, incumbent=incumbent, promote=True,
            reason=(
                f"Candidate beats incumbent on {self.metric} by {improvement:.4f}"
            ),
            metric_deltas=deltas,
        )


def auto_promote(
    registry: ModelRegistry,
    candidate: ModelVersion,
    policy: PromotionPolicy,
    *,
    actor: str = "auto-promoter",
) -> PromotionDecision:
    """Evaluate the policy and (if it passes) move candidate to Production."""
    incumbent = registry.production_version(candidate.model_name)
    decision = policy.decide(candidate, incumbent)
    if decision.promote:
        registry.transition(
            candidate.model_name,
            candidate.version,
            Stage.PRODUCTION,
            actor=actor,
            reason=decision.reason,
        )
    return decision


# -- A/B testing helper ------------------------------------------------


@dataclass
class ABComparison:
    """Side-by-side comparison of two ModelVersions on shared metrics."""

    a: ModelVersion
    b: ModelVersion
    deltas: Dict[str, float]
    winner: Optional[ModelVersion]


def compare_versions(
    a: ModelVersion,
    b: ModelVersion,
    *,
    primary_metric: str,
    higher_is_better: bool = True,
) -> ABComparison:
    deltas: Dict[str, float] = {}
    shared_metrics = set(a.metrics) & set(b.metrics)
    for key in shared_metrics:
        deltas[key] = round(b.metrics[key] - a.metrics[key], 6)
    if primary_metric in deltas:
        # b beats a if delta is positive (higher better) or negative (lower better).
        b_better = deltas[primary_metric] > 0 if higher_is_better else deltas[primary_metric] < 0
        winner = b if b_better else (a if deltas[primary_metric] != 0 else None)
    else:
        winner = None
    return ABComparison(a=a, b=b, deltas=deltas, winner=winner)


def make_version_from_run(
    run: Run,
    *,
    model_name: str,
    artifact_uri: str,
    registry: ModelRegistry,
    description: str = "",
) -> ModelVersion:
    """Extract metrics from an experiment Run and register a model version."""
    metrics: Dict[str, float] = {
        name: entries[-1].value for name, entries in run.metrics.items() if entries
    }
    return registry.register(
        model_name=model_name,
        artifact_uri=artifact_uri,
        run_id=run.run_id,
        metrics=metrics,
        description=description,
    )
