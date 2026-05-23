"""LLM-specific Prometheus metrics."""
from prometheus_client import Counter, Histogram, Gauge


TTFT = Histogram(
    "llm_time_to_first_token_seconds",
    "Time from request received to first token streamed",
    ["model", "tenant"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

TOKEN_THROUGHPUT = Histogram(
    "llm_tokens_per_second",
    "Tokens/s during streaming",
    ["model", "tenant"],
    buckets=(5, 10, 25, 50, 100, 200, 500, 1000),
)

PROMPT_LENGTH = Histogram(
    "llm_prompt_tokens",
    "Prompt length (tokens)",
    ["model", "tenant"],
    buckets=(10, 50, 200, 1000, 4000, 16000, 65000),
)

COMPLETION_LENGTH = Histogram(
    "llm_completion_tokens",
    "Completion length (tokens)",
    ["model", "tenant"],
    buckets=(10, 50, 200, 500, 1000, 2000, 8000),
)

MODEL_USE = Counter(
    "llm_model_calls_total",
    "Calls per model per tenant",
    ["model", "tenant", "tier"],
)

ACTIVE_STREAMS = Gauge(
    "llm_active_streams",
    "Currently-streaming responses",
    ["model"],
)
