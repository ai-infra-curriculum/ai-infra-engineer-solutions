#!/usr/bin/env bash
# Shard a 13B model across 2 GPUs.
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-2-13b-chat-hf \
  --tensor-parallel-size 2 \
  --port 8000
