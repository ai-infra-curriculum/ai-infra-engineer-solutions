"""Run scoring harness; gate CI on result."""
from __future__ import annotations

import argparse
import json
import sys

from judge import judge_score
from reference import bleu, rouge_l, exact_match


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--prompt", required=True)
    p.add_argument("--against", required=True, help="path to golden_set.jsonl")
    p.add_argument("--gate", type=float, default=0.85)
    args = p.parse_args()

    cases = [json.loads(line) for line in open(args.against)]
    scores = []
    for case in cases:
        # In real harness: call the actual LLM app here with prompt=args.prompt
        actual = case["actual"]   # for demo
        expected = case["expected"]
        score = {
            "exact": exact_match(actual, expected),
            "bleu":  bleu(actual, expected),
            "rouge_l": rouge_l(actual, expected),
            "judge": judge_score(actual, expected, case.get("rubric", "")),
        }
        scores.append(score)

    avg = sum(s["judge"] for s in scores) / len(scores)
    print(f"average judge score: {avg:.3f}")
    if avg < args.gate:
        print(f"REGRESSION: {avg:.3f} < gate {args.gate}")
        sys.exit(1)


if __name__ == "__main__":
    main()
