# Prompt Management — Solution

Reference for [learning exercise-10](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-110-llm-infrastructure/exercises/exercise-10-prompt-management/README.md).

Treat prompts like config: versioned, reviewed, A/B-testable, rollback-able.

## Layout

```
exercise-10-prompt-management/
├── README.md
├── prompts/
│   ├── classify_intent/v1.yaml
│   ├── classify_intent/v2.yaml
│   └── classify_intent/active.yaml -> v2.yaml
├── loader.py
├── ab_test.py
└── ci-examples/prompt-pr.yml         # validate + run scoring on PR
```
