"""Baseline: vanilla HuggingFace generate(), batch=1."""
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


def main():
    name = "mistralai/Mistral-7B-Instruct-v0.2"
    tok = AutoTokenizer.from_pretrained(name)
    model = AutoModelForCausalLM.from_pretrained(name, torch_dtype=torch.float16,
                                                  device_map="cuda")
    model.train(False)

    prompt = "Explain rate limiting in 3 sentences."
    inp = tok(prompt, return_tensors="pt").to("cuda")
    # Warmup
    model.generate(**inp, max_new_tokens=20)

    total_tokens = 0
    t0 = time.perf_counter()
    for _ in range(20):
        with torch.inference_mode():
            out = model.generate(**inp, max_new_tokens=128, do_sample=False)
        total_tokens += out.shape[1] - inp.input_ids.shape[1]
    elapsed = time.perf_counter() - t0
    print(f"baseline: {total_tokens / elapsed:.1f} tok/s")


if __name__ == "__main__":
    main()
