# GPU Training Container — Solution

Reference for [learning exercise-03](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-103-containerization/exercises/exercise-03-gpu-container.md).

```bash
docker build -t mnist-gpu .
docker run --rm --gpus all mnist-gpu
# inside, pynvml logs per-epoch memory used
```
