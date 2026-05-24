# Template Catalog — `mlapi-gen`

The five FastAPI-ML templates this generator produces, in detail. Each template renders a fully working FastAPI service, tests, Dockerfile, and a `pyproject.toml` you can extend. Templates use Jinja2 — anything `{{ wrapped }}` in `templates/` is a substitution point.

For implementation details (how the engine renders, where templates live on disk), see `src/mlapi_gen/template_engine.py` and the STEP_BY_STEP guide.

---

## Quick comparison

| Template | Inference shape | ML library | Model artifact | Best for |
|---|---|---|---|---|
| `image_classification` | image → label | torchvision / timm | `.pt` / `.safetensors` | CV classifiers, embedding endpoints |
| `text_classification` | text → label | transformers | HF Hub repo or local dir | Sentiment, intent, moderation |
| `object_detection` | image → boxes | ultralytics / torchvision | `.pt` / ONNX | Detection, segmentation outputs |
| `time_series` | array → array | statsmodels / darts / torch | `.pkl` / `.pt` | Forecasting, anomaly scoring |
| `generic` | JSON in → JSON out | bring-your-own | bring-your-own | Custom pipelines, multi-model services |

All templates include: `/health`, `/ready`, `/metrics` (Prometheus), structured JSON logging, request-id middleware, configurable rate limiting, and OpenAPI docs at `/docs`.

---

## 1. `image_classification`

### Target use case

A single-image classifier endpoint. You upload an image, the service returns top-K predicted classes with confidence scores.

Real-world fits: content moderation, product categorization, defect detection, simple medical imaging triage.

### Project layout (rendered)

```
my-image-api/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, routes mounted
│   ├── api/
│   │   ├── __init__.py
│   │   ├── endpoints.py        # POST /v1/predict, POST /v1/predict/batch
│   │   └── deps.py             # Dependency providers (model, logger)
│   ├── core/
│   │   ├── config.py           # Pydantic Settings
│   │   ├── logging.py
│   │   └── security.py         # API key auth (optional)
│   ├── models/
│   │   ├── classifier.py       # Wraps the model, exposes .predict()
│   │   └── schemas.py          # PredictRequest, PredictResponse, ClassScore
│   └── preprocessing/
│       └── image.py            # PIL load, normalize, tensor conversion
├── tests/
│   ├── conftest.py             # Fixture: in-process app + sample image
│   ├── test_health.py
│   ├── test_predict.py
│   └── test_predict_batch.py
├── models/                     # Where artifacts go (gitignored)
│   └── .gitkeep
├── Dockerfile                  # multi-stage, slim runtime
├── docker-compose.yml          # api + Prometheus + Grafana
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── README.md
└── .github/workflows/test.yml
```

### Key dependencies (pinned in `requirements.txt`)

```
fastapi==0.110.*
uvicorn[standard]==0.27.*
pydantic==2.6.*
pydantic-settings==2.2.*
torch==2.3.*
torchvision==0.18.*
Pillow==10.3.*
python-multipart==0.0.9
prometheus-client==0.20.*
structlog==24.1.*
```

### Customization points

| Point | How |
|---|---|
| Model architecture | Replace `app/models/classifier.py:load_model()`. Default loads a torchvision ResNet-50 with ImageNet weights. |
| Class labels | Edit `app/data/labels.json` (rendered by the template). |
| Preprocessing | `app/preprocessing/image.py` — resize, normalization mean/std. |
| Top-K | `POST /v1/predict?top_k=N` (default 5, max from `config.MAX_TOP_K`). |
| Batch endpoint | Already wired — accepts up to `BATCH_MAX_SIZE` images. |
| GPU vs CPU | Set `DEVICE=cuda` env var. Falls back to CPU on init if CUDA unavailable. |
| Half-precision | `MODEL_DTYPE=fp16` env var. |
| Model artifact loading | `MODEL_PATH=models/resnet50.pt` or `MODEL_NAME=resnet50` (torchvision name). |

### Example generated `endpoints.py`

```python
@router.post("/predict", response_model=PredictResponse)
async def predict(
    file: UploadFile = File(...),
    top_k: int = Query(default=5, ge=1, le=settings.MAX_TOP_K),
    classifier: Classifier = Depends(get_classifier),
) -> PredictResponse:
    raw = await file.read()
    image = load_and_preprocess(raw, target_size=settings.INPUT_SIZE)
    scores = classifier.predict(image, top_k=top_k)
    return PredictResponse(model=settings.MODEL_NAME, predictions=scores)
```

### Where to look first

1. `app/models/classifier.py` — drop in your model.
2. `app/data/labels.json` — set your class names.
3. `tests/test_predict.py` — add a sample input image and assert the right class wins.

---

## 2. `text_classification`

### Target use case

Single-text classification: sentiment, intent, topic, moderation flags.

Real-world fits: support ticket routing, comment moderation, intent detection ahead of a downstream agent.

### Project layout (rendered)

```
my-text-api/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── endpoints.py        # POST /v1/classify, POST /v1/classify/batch, GET /v1/labels
│   │   └── deps.py
│   ├── core/
│   │   ├── config.py
│   │   ├── logging.py
│   │   └── security.py
│   ├── models/
│   │   ├── classifier.py       # transformers AutoModelForSequenceClassification
│   │   ├── tokenizer.py
│   │   └── schemas.py
│   └── postprocessing/
│       └── softmax.py
├── tests/
│   ├── conftest.py
│   ├── test_classify.py
│   └── test_batch.py
├── models/
│   └── .gitkeep
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml
└── README.md
```

### Key dependencies

```
fastapi==0.110.*
uvicorn[standard]==0.27.*
pydantic==2.6.*
transformers==4.40.*
torch==2.3.*
safetensors==0.4.*
sentencepiece==0.2.*
tokenizers==0.19.*
```

### Customization points

| Point | How |
|---|---|
| Base model | `MODEL_NAME=distilbert-base-uncased-finetuned-sst-2-english` (default), any HF Hub `AutoModelForSequenceClassification` works. |
| Local checkpoint | `MODEL_PATH=./models/my-finetune` overrides `MODEL_NAME`. |
| Tokenizer | Auto-loaded; `MAX_LENGTH` env var controls truncation. |
| Multi-label | Set `MULTI_LABEL=true`. Switches from `argmax` to per-label sigmoid + threshold. |
| Confidence threshold | `MIN_CONFIDENCE=0.5`. |
| Device + precision | Same `DEVICE` / `MODEL_DTYPE` env vars as `image_classification`. |
| Streaming response | Not included — text classification is small. Add if you need it. |

### Example generated endpoint

```python
@router.post("/classify", response_model=ClassifyResponse)
async def classify(
    payload: ClassifyRequest,
    classifier: TextClassifier = Depends(get_classifier),
) -> ClassifyResponse:
    if not payload.text.strip():
        raise HTTPException(422, "text must be non-empty")
    scores = classifier.predict(payload.text)
    return ClassifyResponse(
        text=payload.text,
        scores=scores,
        top_label=max(scores, key=lambda s: s.score).label,
    )
```

### Where to look first

1. `app/models/classifier.py` — `load_model()` selects model + tokenizer; swap for fine-tune.
2. `app/api/endpoints.py` — change input schema if you want extra metadata fields.
3. `tests/test_classify.py` — sample inputs and expected labels for your task.

---

## 3. `object_detection`

### Target use case

Image → bounding boxes + class + confidence. Optionally instance masks.

Real-world fits: visual quality control on a production line, retail shelf scanning, surveillance counting, AR overlay backends.

### Project layout (rendered)

```
my-detector-api/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── endpoints.py        # POST /v1/detect, POST /v1/detect/visualize
│   │   └── deps.py
│   ├── core/
│   │   ├── config.py
│   │   └── logging.py
│   ├── models/
│   │   ├── detector.py         # YOLO / Faster R-CNN wrapper
│   │   ├── nms.py              # Class-aware NMS, configurable IoU
│   │   └── schemas.py          # Detection, DetectResponse
│   └── postprocessing/
│       ├── overlay.py          # Optional: draw boxes on image bytes for /visualize
│       └── coordinate.py       # xyxy <-> xywh, normalized <-> pixel
├── tests/
│   ├── conftest.py
│   ├── test_detect.py
│   └── test_nms.py
├── Dockerfile
├── requirements.txt
└── README.md
```

### Key dependencies

```
fastapi==0.110.*
uvicorn[standard]==0.27.*
pydantic==2.6.*
torch==2.3.*
torchvision==0.18.*
ultralytics==8.2.*           # if backend=yolo
opencv-python-headless==4.9.*
Pillow==10.3.*
numpy==1.26.*
```

### Customization points

| Point | How |
|---|---|
| Backend | `DETECTOR_BACKEND=yolo` (default, Ultralytics) or `torchvision-frcnn`. |
| Model size | `MODEL_NAME=yolov8n` / `yolov8s` / `yolov8m` / `yolov8l` / `yolov8x`. |
| Custom weights | `MODEL_PATH=models/my-yolo.pt`. |
| Confidence floor | `CONF_THRESHOLD=0.25` env var. |
| NMS IoU | `IOU_THRESHOLD=0.45`. |
| Max detections | `MAX_DETECTIONS=300`. |
| Image overlay endpoint | `ENABLE_VISUALIZE=true` exposes `POST /v1/detect/visualize` returning PNG with boxes drawn. Adds opencv dependency weight; off by default in prod. |
| Coordinate format in response | `COORD_FORMAT=xyxy` (default) or `xywh` or `normalized`. |

### Example response shape

```json
{
  "model": "yolov8s",
  "image_size": {"width": 1920, "height": 1080},
  "detections": [
    {
      "class_id": 0,
      "class_name": "person",
      "confidence": 0.92,
      "bbox": {"x1": 100.4, "y1": 200.1, "x2": 300.7, "y2": 600.2}
    }
  ],
  "inference_ms": 18.4
}
```

### Where to look first

1. `app/models/detector.py` — set the backend and weights.
2. `app/postprocessing/coordinate.py` — pick the coord convention your downstream consumer expects.
3. `tests/test_detect.py` — sample image and expected detection class to lock the contract.

---

## 4. `time_series`

### Target use case

Forecast the next N values of a series, given the last M observed values. Optionally output confidence intervals.

Real-world fits: load forecasting, ad spend projection, capacity planning, low-stakes anomaly bands.

### Project layout (rendered)

```
my-forecast-api/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── endpoints.py        # POST /v1/forecast, POST /v1/forecast/batch
│   │   └── deps.py
│   ├── core/
│   │   ├── config.py
│   │   └── logging.py
│   ├── models/
│   │   ├── forecaster.py       # ARIMA / Prophet / N-BEATS / LSTM wrapper
│   │   └── schemas.py          # ForecastRequest, ForecastResponse, Series
│   └── preprocessing/
│       ├── validate.py         # Length, monotonicity, NaN checks
│       └── scaling.py          # Standardize input, inverse on output
├── tests/
│   ├── test_forecast.py
│   └── test_validation.py
├── Dockerfile
├── requirements.txt
└── README.md
```

### Key dependencies

```
fastapi==0.110.*
pydantic==2.6.*
numpy==1.26.*
pandas==2.2.*
statsmodels==0.14.*            # if backend=arima
darts==0.29.*                  # if backend=nbeats or tcn
torch==2.3.*                   # if backend includes neural forecaster
prophet==1.1.*                 # optional
```

The template's `requirements.txt` is generated based on the backend you choose at generation time, so you don't pull torch if you're shipping ARIMA only.

### Customization points

| Point | How |
|---|---|
| Backend | `FORECASTER_BACKEND=arima` (default), `prophet`, `nbeats`, `tcn`, `lstm`. |
| Forecast horizon | Per-request `horizon` field; clamped to `MAX_HORIZON`. |
| Confidence intervals | `RETURN_CI=true` adds `lower`/`upper` arrays at configured `CI_LEVEL` (default 0.95). |
| Input length | Validation enforces `MIN_INPUT_LENGTH <= len(series) <= MAX_INPUT_LENGTH`. |
| Missing values | `MISSING_STRATEGY=interpolate` / `error` / `drop`. |
| Exogenous variables | Set `SUPPORT_EXOGENOUS=true` to add `exogenous` field to request schema; only Prophet and Darts backends use them. |
| Model retraining | Out of scope — this is a serving template. Pair with a training pipeline that drops new artifacts into `models/`. |

### Example request / response

```json
// request
{
  "series": [100, 102, 105, 103, 108, 110, 115],
  "horizon": 3,
  "return_ci": true,
  "ci_level": 0.95
}

// response
{
  "model": "arima(1,1,1)",
  "forecast": [117.2, 119.8, 122.1],
  "ci_lower": [113.4, 114.6, 115.9],
  "ci_upper": [121.0, 125.0, 128.3],
  "inference_ms": 28.1
}
```

### Where to look first

1. `app/models/forecaster.py` — backend-specific. Read which one your template generated.
2. `app/preprocessing/validate.py` — most production bugs in forecasting APIs are bad input shape; make sure the validator matches your domain.
3. `tests/test_forecast.py` — pin a deterministic synthetic series and the expected horizon output, so regressions on model upgrade are visible.

---

## 5. `generic`

### Target use case

The escape hatch. When your shape doesn't fit any of the above (recommender, multimodal, embedding-only, agent backend), the generic template gives you the production scaffolding without committing to an inference contract.

Real-world fits: anything custom. Use this when you want the observability, security, and CI plumbing without rewriting it.

### Project layout (rendered)

```
my-generic-api/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── endpoints.py        # POST /v1/predict, POST /v1/predict/batch
│   │   └── deps.py             # get_model() — REPLACE THIS
│   ├── core/
│   │   ├── config.py
│   │   └── logging.py
│   ├── models/
│   │   ├── predictor.py        # ModelProtocol — implement .predict(input) -> output
│   │   └── schemas.py          # PredictRequest, PredictResponse (intentionally permissive)
│   └── preprocessing/
│       └── validate.py         # Hook for your domain validation
├── tests/
│   ├── conftest.py             # mock predictor fixture
│   └── test_predict.py
├── Dockerfile
├── requirements.txt
└── README.md
```

### Key dependencies

Minimal — only what FastAPI itself needs. You add the ML library:

```
fastapi==0.110.*
uvicorn[standard]==0.27.*
pydantic==2.6.*
pydantic-settings==2.2.*
prometheus-client==0.20.*
structlog==24.1.*
```

### Customization points

The template **does not** ship a model. It ships a `Protocol`:

```python
# app/models/predictor.py
from typing import Protocol, Any

class ModelProtocol(Protocol):
    def predict(self, input: Any) -> Any: ...
    def warmup(self) -> None: ...
    def health(self) -> bool: ...
```

You replace `MyModel` with whatever your inference is. Everything else (rate limiting, auth, metrics, logging) is wired and stays.

The `PredictRequest` and `PredictResponse` schemas use `dict[str, Any]` by default — open. You should narrow them once you know your contract. The template marks the spots with `# TODO: narrow this schema`.

### Multi-model serving

The generic template includes a `models/registry.py` you can flip on with `--with-multi-model` at generation time. It exposes:

- `POST /v1/predict?model=name` — route to a named model.
- `GET /v1/models` — list available models with health.
- Model versioning via `?version=v3`.

Each registered model implements `ModelProtocol`. The registry hot-reloads from `models/registry.yaml`.

### Where to look first

1. `app/models/predictor.py` — implement your model class against the protocol.
2. `app/api/endpoints.py` — narrow the request/response schemas once your contract is firm.
3. `app/core/config.py` — add any new env vars your model needs.

---

## Generation flags reference

All templates accept these `mlapi-gen generate` flags. They control which optional surfaces are rendered.

| Flag | Default | Effect |
|---|---|---|
| `--with-auth` | off | Adds API key auth via header `X-API-Key`. Keys configured via `API_KEYS` env. |
| `--with-rate-limiting` | off | Adds in-memory token-bucket limiter. Replace with Redis for production multi-replica. |
| `--with-monitoring` | on (Prometheus only) | Adds Grafana dashboards JSON in `monitoring/` and a docker-compose service. |
| `--with-cors` | off | Enables CORS middleware. Origins via `CORS_ORIGINS` env (comma-sep). |
| `--with-otel` | off | Adds OpenTelemetry instrumentation. Endpoint via `OTEL_EXPORTER_OTLP_ENDPOINT`. |
| `--with-async-queue` | off | Adds a Celery + Redis worker layout. Useful when inference is > 5s. |
| `--with-multi-model` | off (generic only) | Renders the multi-model registry. |
| `--python <ver>` | 3.11 | Python version pin in `pyproject.toml` and Dockerfile. |
| `--no-docker` | off | Skips Dockerfile and docker-compose.yml. |
| `--no-ci` | off | Skips `.github/workflows/`. |
| `--interactive` | off | Walks you through all options conversationally. |

---

## Adding a new template

The templates live in `templates/<template-name>/` and are Jinja2-rendered through `src/mlapi_gen/template_engine.py`. To add one:

1. Create `templates/<name>/` mirroring the layout of an existing template.
2. Add the template name to `TEMPLATE_CHOICES` in `src/mlapi_gen/cli.py`.
3. Add a `TemplateMetadata` entry in `src/mlapi_gen/templates_registry.py` (name, description, required deps).
4. Add tests under `tests/templates/test_<name>.py` that generate the template into a tmp dir and assert the rendered project's tests pass.
5. Add an entry here in this catalog.

Common pitfalls:

- Don't hard-code paths in templates; use the `{{ project_slug }}` substitution.
- Keep the same env-var naming convention (`MODEL_PATH`, `MODEL_NAME`, `DEVICE`) so users moving between templates have a consistent mental model.
- Always include `/health`, `/ready`, `/metrics` — the monitoring stack assumes these.

---

## When to use which

- Your inference is **vision and you have an off-the-shelf model**: `image_classification` (single label) or `object_detection` (boxes).
- Your inference is **text on a Transformer**: `text_classification`.
- Your inference is **forecasting numbers given numbers**: `time_series`.
- **Anything else, or you're combining multiple models**: `generic`. Don't bend one of the others to fit; you'll fight the scaffolding.
