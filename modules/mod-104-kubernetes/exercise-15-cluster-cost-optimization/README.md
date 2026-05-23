# K8s Cluster Cost Optimization — Solution

Reference for [learning exercise-15](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-104-kubernetes/exercises/exercise-15-cluster-cost-optimization/README.md).

5 techniques; cumulative ~55% savings on a mid-size cluster.

```
exercise-15-cluster-cost-optimization/
├── README.md, RESULTS.md
├── audit/
│   ├── rightsize-report.py     # Goldilocks-style recommendation
│   └── idle-detector.py
├── karpenter/
│   ├── nodepool.yaml           # Karpenter NodePool with spot + on-demand
│   └── ec2nodeclass.yaml
└── storage/tiering.yaml         # gp3 default + cheaper gp2/cold class
```
