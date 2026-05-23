# Bug 2: OOM

## Symptom
Container exits after ~10 seconds with exit code 137. No application traceback in logs.

## Diagnosis path

1. `docker inspect <id> | jq '.[0].State'`:
   ```json
   { "OOMKilled": true, "ExitCode": 137, "Status": "exited" }
   ```
   This is unambiguous: the kernel killed the process for exceeding the cgroup memory limit.

2. `docker inspect` also reports `HostConfig.Memory: 2147483648` (2GB) — the configured limit.

3. The application tried to allocate a 13B-element float tensor = ~52GB. Far above the limit.

## Fix
Two paths:
- **Raise the limit** if the workload genuinely needs it: `--memory=64g`.
- **Reduce the workload** (quantize, paged loading, smaller model). Better long-term answer.

## Lesson
`OOMKilled: true` + exit code 137 = cgroup OOM. Don't confuse with application-level `MemoryError`, which would appear in logs with a Python traceback.
