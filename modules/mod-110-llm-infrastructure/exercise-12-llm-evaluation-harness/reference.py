"""Reference-based metrics."""
from __future__ import annotations


def exact_match(actual: str, expected: str) -> float:
    return 1.0 if actual.strip().lower() == expected.strip().lower() else 0.0


def bleu(actual: str, expected: str) -> float:
    try:
        from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
        return sentence_bleu([expected.split()], actual.split(),
                              smoothing_function=SmoothingFunction().method1)
    except Exception:
        return 0.0


def rouge_l(actual: str, expected: str) -> float:
    try:
        from rouge_score import rouge_scorer
        scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
        return scorer.score(expected, actual)["rougeL"].fmeasure
    except Exception:
        return 0.0
