# syntax=docker/dockerfile:1
# Cache-optimized PyTorch image build.
# Reference: https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-103-containerization/exercises/exercise-07-buildkit-cache-optimization/README.md

FROM python:3.11-slim AS deps

WORKDIR /app
COPY requirements.txt .

# Cache mount: pip wheel cache survives across builds.
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    pip install --user -r requirements.txt

# Cache mount for HuggingFace + torch weights. The cache mount survives across
# builds but is not part of the layer, so copy the warmed weights into a normal
# path that the runtime stage can pull from.
COPY warmup_cache.py .
RUN --mount=type=cache,target=/root/.cache/huggingface,sharing=locked \
    --mount=type=cache,target=/root/.cache/torch,sharing=locked \
    --mount=type=secret,id=hf_token,env=HF_TOKEN \
    python warmup_cache.py \
    && mkdir -p /opt/hf-cache \
    && cp -a /root/.cache/huggingface/. /opt/hf-cache/

FROM python:3.11-slim
COPY --from=deps /root/.local /root/.local
COPY --from=deps /opt/hf-cache /root/.cache/huggingface
ENV PATH=/root/.local/bin:$PATH \
    HF_HOME=/root/.cache/huggingface
WORKDIR /app
COPY app.py .
CMD ["python", "app.py"]
