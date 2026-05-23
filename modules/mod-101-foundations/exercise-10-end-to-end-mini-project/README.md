# Mini-Platform Capstone — Solution

Reference for [learning exercise-10-end-to-end-mini-project](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/tree/main/lessons/mod-101-foundations/exercises/exercise-10-end-to-end-mini-project/README.md).

Integrates the outputs of ex-07 (cloud-onboard), ex-08 (model-serve), and ex-09 (test suite) into a `make up`/`make down` mini-platform.

## Layout

```
exercise-10-end-to-end-mini-project/
├── README.md
├── Makefile                # the orchestration entry point
├── infra/
│   ├── onboard.sh          # wraps cloud-onboard init
│   └── kind-config.yaml
├── deploy/
│   ├── deployment.yaml, service.yaml, hpa.yaml, servicemonitor.yaml
├── monitoring/
│   ├── values.yaml
│   └── grafana-dashboard.json
└── loadtest/
    └── locustfile.py
```

The actual application code lives in ex-08; this exercise is the integration layer.

## Demo flow

```bash
make up          # ~4 min: cluster + ingress + prom stack + app + port-forwards
make load        # 30s of synthetic load
# Open http://localhost:3000 (Grafana)  /  http://localhost:8080 (api)
make down        # cleans everything
```
