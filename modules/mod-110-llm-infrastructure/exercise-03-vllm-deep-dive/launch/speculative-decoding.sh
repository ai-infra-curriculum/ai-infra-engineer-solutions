#!/usr/bin/env bash
# Use a small draft model to propose tokens; large model verifies.
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-2-70b-chat-hf \
  --tensor-parallel-size 4 \
  --speculative-model meta-llama/Llama-2-7b-chat-hf \
  --num-speculative-tokens 5 \
  --port 8000
