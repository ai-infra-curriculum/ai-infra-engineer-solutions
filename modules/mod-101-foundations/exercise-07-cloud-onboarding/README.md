# cloud-onboard CLI — Solution

Reference solution for [learning exercise-07-cloud-onboarding](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/tree/main/lessons/mod-101-foundations/exercises/exercise-07-cloud-onboarding/README.md).

Per-user cloud sandbox provisioner: VPC + bucket + IAM scoped per user.

## Layout

```
exercise-07-cloud-onboarding/
├── README.md
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── cli.py
│   ├── state.py
│   └── providers/
│       ├── __init__.py
│       ├── base.py
│       └── aws.py
└── tests/
    └── test_aws.py
```

## Quick start

```bash
./scripts/setup.sh
cloud-onboard init --user alice --provider aws --region us-west-2
cloud-onboard status --user alice
cloud-onboard destroy --user alice
```
