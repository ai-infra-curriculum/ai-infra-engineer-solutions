#!/usr/bin/env bash
# Serve base + 2 adapters via vLLM hot-swap.
python -m vllm.entrypoints.openai.api_server \
  --model mistralai/Mistral-7B-Instruct-v0.2 \
  --enable-lora \
  --lora-modules dolly=adapters/dolly-lora qlora=adapters/qlora-13b \
  --max-loras 4 --max-lora-rank 64 --port 8000
