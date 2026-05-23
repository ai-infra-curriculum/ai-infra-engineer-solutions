# Guardrail Test Results

Against the 14-attack suite:
- **Blocked**: 8 (all injection attempts)
- **Sanitized**: 3 (PII redacted, request still proceeds)
- **Passed**: 3 (innocuous queries)

## False-positive rate

On 1000 benign queries from production traffic:
- 12 blocked unnecessarily (1.2%); investigation found 8 contained URLs with "ignore" in path; pattern tightened to require word boundary.
- After tightening: 4 false positives (0.4%).

## Recommendations

- Keep input + output guards composable; new attack patterns require only adding regex/check.
- Layer 4 of defense: rate-limit + abuse detection (mod-110 ex-07).
- Llama Guard or OpenAI moderation API is a stronger second layer for content-policy violations.
