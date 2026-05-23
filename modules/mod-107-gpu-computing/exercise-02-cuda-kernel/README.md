# Custom CUDA Kernel + PyTorch Extension — Solution

Reference for [learning exercise-02-cuda-kernel](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/tree/main/lessons/mod-107-gpu-computing/exercises/exercise-02-cuda-kernel/README.md).

A vector-add CUDA kernel wrapped as a PyTorch CUDA extension, benchmarked against `torch.add`.

## Layout

```
exercise-02-cuda-kernel/
├── README.md, setup.py
├── vector_add.cu       # CUDA kernel
├── my_ops.cpp          # pybind11 wrapper
└── bench.py            # comparison
```

## Build + run

```bash
pip install torch pybind11
pip install -e .
python bench.py
```
