# Container Runtime Debugging — Solution

Reference for [learning exercise-09](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-103-containerization/exercises/exercise-09-runtime-debugging/README.md).

Each broken container is in its own subdirectory with:
- `Dockerfile.broken` — the bug
- `Dockerfile.fixed` — corrected version
- `DIAGNOSIS.md` — the methodology used to find it

## Layout

```
exercise-09-runtime-debugging/
├── README.md, RUNBOOK.md
├── bug-1-bind-address/
├── bug-2-oom/
└── bug-3-permission/
```

## RUNBOOK.md

See `RUNBOOK.md` for the general "container is up but broken" methodology
applicable beyond these specific bugs.
