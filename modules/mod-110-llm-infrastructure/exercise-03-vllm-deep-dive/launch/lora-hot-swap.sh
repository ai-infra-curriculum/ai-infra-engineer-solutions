#!/usr/bin/env bash
# Serve base model with multiple LoRA adapters; clients pick by name.
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-2-7b-chat-hf \
  --enable-lora \
  --max-loras 4 \
  --max-lora-rank 16 \
  --lora-modules sql=adapters/llama2-sql legal=adapters/llama2-legal \
  --port 8000

# Request:
# curl ... -H "Content-Type: application/json" \
#   -d '{"model":"sql","prompt":"Translate to SQL: count users by country"}'
