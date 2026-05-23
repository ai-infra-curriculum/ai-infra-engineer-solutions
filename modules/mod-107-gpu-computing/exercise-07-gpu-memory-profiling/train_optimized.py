"""Optimized: gradient checkpointing + Adam8bit + bf16 autocast."""
import torch
import bitsandbytes as bnb
from transformers import AutoModelForCausalLM


def main():
    model = AutoModelForCausalLM.from_pretrained("gpt2-medium").cuda()
    model.gradient_checkpointing_enable()    # halve activation memory
    opt = bnb.optim.AdamW8bit(model.parameters(), lr=1e-5)
    for step in range(5):
        x = torch.randint(0, 50000, (16, 512), device="cuda")
        with torch.amp.autocast("cuda", dtype=torch.bfloat16):
            loss = model(x, labels=x).loss
        loss.backward()
        opt.step(); opt.zero_grad()
        print(f"step {step} peak_mem={torch.cuda.max_memory_allocated()/1e9:.2f} GB")


if __name__ == "__main__":
    main()
