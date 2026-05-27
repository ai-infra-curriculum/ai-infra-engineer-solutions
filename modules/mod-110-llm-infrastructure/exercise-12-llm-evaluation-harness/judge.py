"""LLM-as-judge: ask a stronger model to score the candidate."""
import json
import os

import httpx


JUDGE_PROMPT = """You are an evaluation rater. Given an expected answer and an actual answer, rate how well the actual answer matches the expected on a scale of 0.0 to 1.0.

Rubric: {rubric}

Expected: {expected}
Actual:   {actual}

Return JSON: {{"score": float, "reasoning": "..."}}"""


def judge_score(actual: str, expected: str, rubric: str = "") -> float:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return 0.5     # CI without key returns neutral
    r = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user",
                           "content": JUDGE_PROMPT.format(rubric=rubric,
                                                          expected=expected, actual=actual)}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        },
        timeout=60,
    )
    return float(json.loads(r.json()["choices"][0]["message"]["content"])["score"])
