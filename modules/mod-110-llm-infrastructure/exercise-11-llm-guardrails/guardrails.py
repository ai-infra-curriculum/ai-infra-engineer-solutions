"""Composable guard pipeline."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class GuardResult:
    allowed: bool
    reason: str = ""
    sanitized_text: str | None = None


class InputGuard:
    """Input-side guards run before sending to the LLM."""

    INJECTION_PATTERNS = [
        re.compile(r"ignore (the )?(previous|prior|above) instructions", re.I),
        re.compile(r"you are (now |from now on )?(in )?(developer|admin|root) mode", re.I),
        re.compile(r"\bsudo\b", re.I),
        re.compile(r"reveal (your |the )?(system )?prompt", re.I),
    ]

    PII_PATTERNS = [
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),                       # US SSN
        re.compile(r"\b\d{16}\b"),                                    # naive credit card
        re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),  # email
    ]

    @classmethod
    def check(cls, text: str) -> GuardResult:
        for p in cls.INJECTION_PATTERNS:
            if p.search(text):
                return GuardResult(allowed=False, reason=f"injection: {p.pattern!r}")

        sanitized = text
        for p in cls.PII_PATTERNS:
            sanitized = p.sub("[REDACTED]", sanitized)
        return GuardResult(allowed=True, sanitized_text=sanitized)


class OutputGuard:
    """Output-side guards run on LLM response before returning to user."""

    REFUSAL_PHRASES = [
        "i cannot help", "i can't help", "i'm not able to help",
        "as an ai", "i don't have personal opinions",
    ]

    @classmethod
    def check(cls, text: str) -> GuardResult:
        lower = text.lower()
        if any(p in lower for p in cls.REFUSAL_PHRASES):
            return GuardResult(allowed=True, sanitized_text=text)        # let through
        # Redact any leaked PII from the output too
        return GuardResult(allowed=True, sanitized_text=InputGuard.check(text).sanitized_text or text)


def moderate(text: str) -> GuardResult:
    """Call external moderation API. Sketch: would call OpenAI moderation / Llama Guard."""
    return GuardResult(allowed=True)


def guarded_call(prompt: str) -> dict:
    """Pipeline: input guard → moderation → llm → output guard."""
    g1 = InputGuard.check(prompt)
    if not g1.allowed:
        return {"refused": True, "reason": g1.reason}

    g2 = moderate(g1.sanitized_text or prompt)
    if not g2.allowed:
        return {"refused": True, "reason": g2.reason}

    # Call LLM here (omitted)
    response = f"<response to: {g1.sanitized_text or prompt}>"

    g3 = OutputGuard.check(response)
    return {"refused": False, "response": g3.sanitized_text}
