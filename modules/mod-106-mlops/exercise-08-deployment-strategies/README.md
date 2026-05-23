# Model Deployment Strategies — Solution

Reference for [learning exercise-08](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-106-mlops/exercises/exercise-08-deployment-strategies/README.md).

Four strategies + measured comparison.

| Strategy | Risk | Speed | Implementation |
|---|---|---|---|
| Rolling | medium | fast | `kubectl set image` |
| Blue-Green | low | medium | duplicate deployment + service switch |
| Canary | low | slow | Argo Rollouts + analysis template |
| Shadow | none | n/a | Istio mirror to candidate, ignore response |

## Layout

```
exercise-08-deployment-strategies/
├── README.md, COMPARISON.md
├── rolling/deployment.yaml
├── blue-green/{deploy-blue.yaml, deploy-green.yaml, switch.sh}
├── canary/rollout.yaml          # Argo Rollouts
├── shadow/virtualservice.yaml   # Istio mirror
└── scripts/measure.sh           # rollout-time + blast-radius
```
