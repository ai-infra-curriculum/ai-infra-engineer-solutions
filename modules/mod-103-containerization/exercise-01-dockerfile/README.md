# ML Dockerfile — Solution

Reference for [learning exercise-01](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-103-containerization/exercises/exercise-01-dockerfile.md).

Multi-stage Dockerfile + non-root + healthcheck + CPU-only torch wheel.

## Build + run

```bash
docker build -t resnet-classifier:0.1 .
docker run --rm -p 8000:8000 resnet-classifier:0.1
curl -F file=@cat.jpg http://localhost:8000/predict
```
