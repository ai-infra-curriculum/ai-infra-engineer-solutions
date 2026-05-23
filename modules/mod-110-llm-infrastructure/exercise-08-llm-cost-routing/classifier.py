"""Heuristic + small-LLM classifier: chooses initial tier."""
from __future__ import annotations


def classify(prompt: str) -> str:
    """Return 'small' / 'medium' / 'large' based on heuristic signals."""
    words = prompt.split()
    n = len(words)

    if n < 20 and "?" in prompt:
        return "small"        # quick QA

    if any(kw in prompt.lower() for kw in ["code", "function", "implement", "fix"]):
        return "medium"       # coding tasks need medium quality

    if any(kw in prompt.lower() for kw in ["plan", "design", "architect", "compare",
                                             "synthesize", "summarize across"]):
        return "large"        # multi-step reasoning needs large

    if n > 500:
        return "large"        # long context tasks

    return "medium"           # default mid-tier
