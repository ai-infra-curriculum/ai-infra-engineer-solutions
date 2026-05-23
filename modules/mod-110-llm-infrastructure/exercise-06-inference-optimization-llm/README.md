# LLM Inference Optimization Chain — Solution

Reference for [learning exercise-06](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-110-llm-infrastructure/exercises/exercise-06-inference-optimization-llm/README.md).

Cumulative chain on a 7B model.

## Files

- `baseline_hf.py` — vanilla HuggingFace, batch=1
- `vllm_baseline.py` — vLLM continuous batching
- `vllm_prefix.py` — + prefix caching
- `awq_quant.sh` — quantize to AWQ
- `vllm_awq.py` — serve AWQ + all the above
- `RESULTS.md` — cumulative tokens/s

## Result

| Stage | Tok/s | Vs baseline |
|---|---|---|
| HF transformers batch=1 | 35 | 1.0× |
| vLLM continuous batching, batch=32 | 1,840 | 53× |
| + prefix caching | 4,200 | 120× |
| + AWQ 4bit | 5,800 | 165× |
