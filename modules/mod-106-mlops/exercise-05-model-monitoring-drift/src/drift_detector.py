"""
Drift Detector

Statistical tests for data + concept drift on numeric features:

- KS test (Kolmogorov-Smirnov): tests whether two samples come from the
  same distribution. Suitable for continuous features.
- PSI (Population Stability Index): binned comparison between reference
  and live distributions. Common in financial-services monitoring.
- Chi-square test: categorical drift over fixed bins.

All tests are implemented in pure Python (no scipy) so the curriculum
solution stays portable. The KS test uses the standard asymptotic
two-sample formula; PSI uses the conventional 10-bin equal-width split
with epsilon smoothing.
"""

from __future__ import annotations

import logging
import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Iterable, List, Optional, Tuple


logger = logging.getLogger(__name__)


class DriftSeverity(str, Enum):
    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"


class DriftTest(str, Enum):
    KS = "ks"
    PSI = "psi"
    CHI_SQUARE = "chi_square"


@dataclass
class DriftResult:
    """One drift-test outcome for one feature."""

    feature: str
    test: DriftTest
    statistic: float
    p_value: Optional[float]
    threshold: float
    detected: bool
    severity: DriftSeverity
    reference_size: int
    live_size: int
    detail: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# -- KS test ------------------------------------------------------------


def ks_statistic(reference: List[float], live: List[float]) -> float:
    """Two-sample Kolmogorov-Smirnov statistic D."""
    if not reference or not live:
        return 0.0
    ref_sorted = sorted(reference)
    live_sorted = sorted(live)
    i = j = 0
    cdf_ref = cdf_live = 0.0
    n_ref = len(ref_sorted)
    n_live = len(live_sorted)
    max_d = 0.0
    while i < n_ref and j < n_live:
        if ref_sorted[i] <= live_sorted[j]:
            i += 1
            cdf_ref = i / n_ref
        else:
            j += 1
            cdf_live = j / n_live
        diff = abs(cdf_ref - cdf_live)
        if diff > max_d:
            max_d = diff
    # Drain tail.
    while i < n_ref:
        i += 1
        cdf_ref = i / n_ref
        diff = abs(cdf_ref - cdf_live)
        if diff > max_d:
            max_d = diff
    while j < n_live:
        j += 1
        cdf_live = j / n_live
        diff = abs(cdf_ref - cdf_live)
        if diff > max_d:
            max_d = diff
    return max_d


def ks_p_value(d: float, n: int, m: int) -> float:
    """Asymptotic two-sample KS p-value approximation."""
    if d <= 0 or n <= 0 or m <= 0:
        return 1.0
    en = math.sqrt(n * m / (n + m))
    arg = (en + 0.12 + 0.11 / en) * d
    if arg <= 0:
        return 1.0
    # Kolmogorov distribution tail series.
    s = 0.0
    fac = 2.0
    sign = 1.0
    for j in range(1, 101):
        term = sign * math.exp(-2.0 * (j * arg) ** 2)
        s += term
        if abs(term) <= 0.001 * abs(s) or abs(term) <= 1e-8:
            return min(max(fac * s, 0.0), 1.0)
        sign = -sign
    return min(max(fac * s, 0.0), 1.0)


def ks_test(
    feature: str,
    reference: List[float],
    live: List[float],
    *,
    significance: float = 0.05,
) -> DriftResult:
    if not reference or not live:
        return DriftResult(
            feature=feature, test=DriftTest.KS, statistic=0.0,
            p_value=1.0, threshold=significance, detected=False,
            severity=DriftSeverity.NONE,
            reference_size=len(reference), live_size=len(live),
            detail="empty sample",
        )
    d = ks_statistic(reference, live)
    p = ks_p_value(d, len(reference), len(live))
    detected = p < significance
    severity = _ks_severity(d)
    return DriftResult(
        feature=feature, test=DriftTest.KS, statistic=round(d, 4),
        p_value=round(p, 6), threshold=significance, detected=detected,
        severity=severity if detected else DriftSeverity.NONE,
        reference_size=len(reference), live_size=len(live),
    )


def _ks_severity(d: float) -> DriftSeverity:
    if d >= 0.3:
        return DriftSeverity.MAJOR
    if d >= 0.15:
        return DriftSeverity.MODERATE
    if d >= 0.05:
        return DriftSeverity.MINOR
    return DriftSeverity.NONE


# -- PSI ----------------------------------------------------------------


def population_stability_index(
    reference: List[float],
    live: List[float],
    *,
    bins: int = 10,
    epsilon: float = 1e-4,
) -> Tuple[float, List[Dict[str, float]]]:
    """PSI plus per-bin breakdown for diagnostic surfaces."""
    if not reference or not live:
        return 0.0, []
    lo = min(min(reference), min(live))
    hi = max(max(reference), max(live))
    if lo == hi:
        return 0.0, []
    edges = [lo + (hi - lo) * i / bins for i in range(bins + 1)]
    edges[-1] = hi + 1e-9  # right edge inclusive on the final bin

    def _bin(values: List[float]) -> List[float]:
        counts = [0.0] * bins
        for v in values:
            for i in range(bins):
                if edges[i] <= v < edges[i + 1]:
                    counts[i] += 1
                    break
        total = sum(counts) or 1
        return [c / total for c in counts]

    ref_dist = _bin(reference)
    live_dist = _bin(live)
    psi = 0.0
    breakdown: List[Dict[str, float]] = []
    for i in range(bins):
        r = max(ref_dist[i], epsilon)
        l = max(live_dist[i], epsilon)
        contribution = (l - r) * math.log(l / r)
        psi += contribution
        breakdown.append({
            "bin_lo": round(edges[i], 4),
            "bin_hi": round(edges[i + 1], 4),
            "reference_pct": round(ref_dist[i], 4),
            "live_pct": round(live_dist[i], 4),
            "psi_contribution": round(contribution, 4),
        })
    return psi, breakdown


def psi_test(
    feature: str,
    reference: List[float],
    live: List[float],
    *,
    minor_threshold: float = 0.10,
    moderate_threshold: float = 0.25,
    bins: int = 10,
) -> DriftResult:
    psi, _ = population_stability_index(reference, live, bins=bins)
    severity = _psi_severity(psi, minor_threshold, moderate_threshold)
    detected = severity is not DriftSeverity.NONE
    return DriftResult(
        feature=feature, test=DriftTest.PSI, statistic=round(psi, 4),
        p_value=None, threshold=moderate_threshold, detected=detected,
        severity=severity,
        reference_size=len(reference), live_size=len(live),
    )


def _psi_severity(psi: float, minor: float, moderate: float) -> DriftSeverity:
    if psi >= moderate * 2:
        return DriftSeverity.MAJOR
    if psi >= moderate:
        return DriftSeverity.MODERATE
    if psi >= minor:
        return DriftSeverity.MINOR
    return DriftSeverity.NONE


# -- Chi-square (categorical) -------------------------------------------


def chi_square_test(
    feature: str,
    reference: List[str],
    live: List[str],
    *,
    significance: float = 0.05,
) -> DriftResult:
    if not reference or not live:
        return DriftResult(
            feature=feature, test=DriftTest.CHI_SQUARE, statistic=0.0,
            p_value=1.0, threshold=significance, detected=False,
            severity=DriftSeverity.NONE,
            reference_size=len(reference), live_size=len(live),
            detail="empty sample",
        )
    categories = sorted(set(reference) | set(live))
    n_ref = len(reference)
    n_live = len(live)

    def _count(values: List[str]) -> Dict[str, int]:
        out = {c: 0 for c in categories}
        for v in values:
            out[v] += 1
        return out

    ref_counts = _count(reference)
    live_counts = _count(live)
    total = n_ref + n_live
    chi2 = 0.0
    for cat in categories:
        ref_observed = ref_counts[cat]
        live_observed = live_counts[cat]
        col_total = ref_observed + live_observed
        if col_total == 0:
            continue
        ref_expected = col_total * (n_ref / total)
        live_expected = col_total * (n_live / total)
        if ref_expected > 0:
            chi2 += (ref_observed - ref_expected) ** 2 / ref_expected
        if live_expected > 0:
            chi2 += (live_observed - live_expected) ** 2 / live_expected
    dof = max(1, len(categories) - 1)
    p = _chi_square_p_value(chi2, dof)
    detected = p < significance
    return DriftResult(
        feature=feature, test=DriftTest.CHI_SQUARE,
        statistic=round(chi2, 4),
        p_value=round(p, 6),
        threshold=significance, detected=detected,
        severity=DriftSeverity.MODERATE if detected else DriftSeverity.NONE,
        reference_size=n_ref, live_size=n_live,
    )


def _chi_square_p_value(chi2: float, dof: int) -> float:
    """Upper-tail p-value of chi-square via the regularized gamma function."""
    if chi2 <= 0:
        return 1.0
    # P-value = 1 - regularized_lower_gamma(dof/2, chi2/2).
    return 1.0 - _regularized_lower_gamma(dof / 2.0, chi2 / 2.0)


def _regularized_lower_gamma(a: float, x: float) -> float:
    if x < 0 or a <= 0:
        return 0.0
    if x < a + 1.0:
        # Series expansion.
        ap = a
        s = 1.0 / a
        delta = s
        for _ in range(200):
            ap += 1.0
            delta *= x / ap
            s += delta
            if abs(delta) < abs(s) * 1e-10:
                break
        return s * math.exp(-x + a * math.log(x) - _log_gamma(a))
    # Continued fraction expansion (complement).
    b = x + 1.0 - a
    c = 1.0 / 1e-30
    d = 1.0 / b
    h = d
    for i in range(1, 200):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < 1e-30:
            d = 1e-30
        c = b + an / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-10:
            break
    return 1.0 - h * math.exp(-x + a * math.log(x) - _log_gamma(a))


def _log_gamma(x: float) -> float:
    # Stirling-series log-gamma. Sufficient for the p-value approximation.
    coeffs = [
        76.18009172947146, -86.50532032941677, 24.01409824083091,
        -1.231739572450155, 0.1208650973866179e-2, -0.5395239384953e-5,
    ]
    y = x
    tmp = x + 5.5
    tmp -= (x + 0.5) * math.log(tmp)
    ser = 1.000000000190015
    for c in coeffs:
        y += 1.0
        ser += c / y
    return -tmp + math.log(2.5066282746310005 * ser / x)


# -- Aggregate driver ----------------------------------------------------


@dataclass
class FeatureSpec:
    name: str
    kind: str  # "numeric" or "categorical"
    test: DriftTest


class DriftDetector:
    """Run drift tests across a configured feature set."""

    def __init__(
        self,
        features: List[FeatureSpec],
        *,
        ks_significance: float = 0.05,
        psi_minor: float = 0.10,
        psi_moderate: float = 0.25,
        chi_square_significance: float = 0.05,
    ):
        self.features = features
        self.ks_significance = ks_significance
        self.psi_minor = psi_minor
        self.psi_moderate = psi_moderate
        self.chi_square_significance = chi_square_significance

    def detect(
        self,
        reference: Dict[str, List],
        live: Dict[str, List],
    ) -> List[DriftResult]:
        results: List[DriftResult] = []
        for spec in self.features:
            ref_vals = reference.get(spec.name, [])
            live_vals = live.get(spec.name, [])
            if spec.test is DriftTest.KS:
                results.append(ks_test(spec.name, ref_vals, live_vals,
                                       significance=self.ks_significance))
            elif spec.test is DriftTest.PSI:
                results.append(psi_test(spec.name, ref_vals, live_vals,
                                        minor_threshold=self.psi_minor,
                                        moderate_threshold=self.psi_moderate))
            elif spec.test is DriftTest.CHI_SQUARE:
                results.append(chi_square_test(spec.name, ref_vals, live_vals,
                                               significance=self.chi_square_significance))
        return results


# -- Concept drift -------------------------------------------------------


@dataclass
class ConceptDriftResult:
    """Tracks model accuracy decay between windows."""

    reference_accuracy: float
    live_accuracy: float
    delta: float
    threshold: float
    detected: bool
    severity: DriftSeverity


def concept_drift_from_accuracy(
    reference_accuracy: float,
    live_accuracy: float,
    *,
    minor_threshold: float = 0.02,
    moderate_threshold: float = 0.05,
) -> ConceptDriftResult:
    delta = reference_accuracy - live_accuracy
    severity = DriftSeverity.NONE
    detected = False
    if delta >= moderate_threshold * 2:
        severity = DriftSeverity.MAJOR
        detected = True
    elif delta >= moderate_threshold:
        severity = DriftSeverity.MODERATE
        detected = True
    elif delta >= minor_threshold:
        severity = DriftSeverity.MINOR
        detected = True
    return ConceptDriftResult(
        reference_accuracy=reference_accuracy,
        live_accuracy=live_accuracy,
        delta=round(delta, 4),
        threshold=moderate_threshold,
        detected=detected,
        severity=severity,
    )


def detect_concept_drift_from_predictions(
    reference_correct: List[bool],
    live_correct: List[bool],
    **kwargs,
) -> ConceptDriftResult:
    ref_acc = (sum(reference_correct) / len(reference_correct)) if reference_correct else 0.0
    live_acc = (sum(live_correct) / len(live_correct)) if live_correct else 0.0
    return concept_drift_from_accuracy(ref_acc, live_acc, **kwargs)
