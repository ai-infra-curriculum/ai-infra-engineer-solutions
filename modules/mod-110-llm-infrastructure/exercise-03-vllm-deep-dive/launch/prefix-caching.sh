#!/usr/bin/env bash
# Reuse KV cache across requests that share a common prefix (e.g., system prompt).
python -m vllm.entrypoints.openai.api_server \
  --model mistralai/Mistral-7B-Instruct-v0.2 \
  --enable-prefix-caching \
  --port 8000
