# PyTorch GPU Training Pipeline — Solution

Reference for [learning exercise-03-pytorch-gpu-pipeline](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/tree/main/lessons/mod-107-gpu-computing/exercises/exercise-03-pytorch-gpu-pipeline/README.md).

ResNet-18 on CIFAR-10 with AMP, gradient accumulation, cosine LR, safetensors checkpoints.

## Layout

```
exercise-03-pytorch-gpu-pipeline/
├── README.md, requirements.txt
├── src/
│   ├── train.py
│   └── infer.py
└── models/         # checkpoints (gitignored)
```

## Run

```bash
./scripts/setup.sh
python -m src.train --epochs 5 --batch-size 512 --accum 4
python -m src.infer --ckpt models/epoch-final.safetensors
```
