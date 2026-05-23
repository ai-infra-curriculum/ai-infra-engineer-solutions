"""vLLM with continuous batching + concurrent requests."""
import asyncio
import time

from vllm import LLM, SamplingParams


def main():
    llm = LLM(model="mistralai/Mistral-7B-Instruct-v0.2", max_model_len=2048)
    prompts = [f"Explain rate limiting in 3 sentences. (#{i})" for i in range(64)]
    sp = SamplingParams(max_tokens=128, temperature=0)

    t0 = time.perf_counter()
    outputs = llm.generate(prompts, sp)
    elapsed = time.perf_counter() - t0
    total_tokens = sum(len(o.outputs[0].token_ids) for o in outputs)
    print(f"vllm baseline: {total_tokens / elapsed:.1f} tok/s")


if __name__ == "__main__":
    main()
