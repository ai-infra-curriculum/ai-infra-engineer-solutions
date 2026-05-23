"""Loads a 'large' tensor. Fails under low memory limit."""
import torch
print("loading 13B-sized tensor...")
x = torch.zeros((13_000_000_000,), dtype=torch.float32)
print("won't get here")
