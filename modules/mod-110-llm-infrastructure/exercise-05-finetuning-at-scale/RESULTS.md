# Fine-Tune Results

| Variant | GPU | Train time | Peak mem | Final loss |
|---|---|---|---|---|
| Mistral-7B LoRA fp16 | 1×L40S | 38 min | 38 GB | 1.42 |
| Llama-13B QLoRA 4bit | 1×L40S | 2 hr 15 min | 22 GB | 1.18 |
| Llama-13B LoRA DDP | 4×A100 | 35 min | 4×72 GB | 1.21 |

## Adapter sizing
- LoRA r=16: ~50 MB
- LoRA r=64: ~200 MB
- vLLM hot-swap: 4 adapters live; first request to a new one ~80ms slower

## Key takeaways
- QLoRA opens 13B fine-tuning to a single 24GB GPU; ~5× cheaper than full fp16.
- DDP gets a 5× wall-clock win, but at 4× the cost — not the right tool for cost-sensitive teams.
- Hot-swap means one base model can serve dozens of domain adapters from one GPU.
