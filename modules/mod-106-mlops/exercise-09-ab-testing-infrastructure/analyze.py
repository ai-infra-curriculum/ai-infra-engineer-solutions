"""Analyze experiment results: t-test + Mann-Whitney + Cohen's d."""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
from scipy import stats


def cohen_d(a: np.ndarray, b: np.ndarray) -> float:
    return (a.mean() - b.mean()) / np.sqrt((a.std(ddof=1)**2 + b.std(ddof=1)**2) / 2)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--exposures", required=True)    # JSONL of exposure + attributed metric
    p.add_argument("--metric", default="conversion")
    args = p.parse_args()

    df = pd.read_json(args.exposures, lines=True)
    control = df[df["variant"] == "control"][args.metric].dropna()
    treatment = df[df["variant"] == "treatment"][args.metric].dropna()

    print(f"control n={len(control)} mean={control.mean():.4f}")
    print(f"treatment n={len(treatment)} mean={treatment.mean():.4f}")
    lift_pct = (treatment.mean() - control.mean()) / control.mean() * 100
    print(f"lift: {lift_pct:+.2f}%")

    t_stat, t_p = stats.ttest_ind(treatment, control, equal_var=False)
    u_stat, u_p = stats.mannwhitneyu(treatment, control, alternative="two-sided")
    d = cohen_d(treatment.values, control.values)

    print(f"Welch's t: t={t_stat:.3f}, p={t_p:.4f}")
    print(f"Mann-Whitney U: U={u_stat:.0f}, p={u_p:.4f}")
    print(f"Cohen's d: {d:.3f}")

    print("\nVerdict:")
    if t_p < 0.05 and lift_pct > 0:
        print(f"  ✓ Significant positive effect (p={t_p:.4f}, lift={lift_pct:+.2f}%)")
    elif t_p < 0.05 and lift_pct < 0:
        print(f"  ✗ Significant NEGATIVE effect (p={t_p:.4f}, lift={lift_pct:+.2f}%)")
    else:
        print(f"  ~ Not significant (p={t_p:.4f}); inconclusive")


if __name__ == "__main__":
    main()
