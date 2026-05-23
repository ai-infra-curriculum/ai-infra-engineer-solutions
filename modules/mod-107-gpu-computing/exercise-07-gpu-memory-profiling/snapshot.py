"""Memory snapshot helper. Upload output to https://pytorch.org/memory_viz."""
import torch
from transformers import AutoModelForCausalLM


def main():
    torch.cuda.memory._record_memory_history(max_entries=100_000)

    model = AutoModelForCausalLM.from_pretrained("gpt2").cuda()
    opt = torch.optim.AdamW(model.parameters(), lr=1e-5)
    for _ in range(3):
        x = torch.randint(0, 50000, (4, 256), device="cuda")
        loss = model(x, labels=x).loss
        loss.backward()
        opt.step(); opt.zero_grad()

    torch.cuda.memory._dump_snapshot("snapshot.bin")
    torch.cuda.memory._record_memory_history(enabled=None)
    print("wrote snapshot.bin (upload to https://pytorch.org/memory_viz)")


if __name__ == "__main__":
    main()
