# Runbook: "Container is up but broken"

## The 5-step methodology

1. **`docker logs <id> --tail 200`** — most bugs surface here. Is the app even starting?

2. **`docker inspect <id> | jq '.[0].State'`** — running? exited? restarting? OOM-killed?
   - `OOMKilled: true` → bug-2 family
   - `ExitCode 137` → SIGKILL (oom or `kill -9`)
   - `ExitCode 139` → segfault

3. **`docker exec -it <id> sh`** — get inside.
   - `netstat -ltn` / `ss -ltn` — is the app listening on the right addr?
     `127.0.0.1:8000` ≠ accessible from host.
   - `ps aux` — is the right process running?
   - `cat /proc/<pid>/limits` — what limits are actually in force?
   - `cat /proc/<pid>/status | grep VmRSS` — current memory.

4. **If exec doesn't work** (distroless / scratch image), use an ephemeral debug container:
   ```bash
   kubectl debug -it <pod> --image=busybox --target=<container>
   docker run --rm -it --pid container:<id> --net container:<id> busybox sh
   ```

5. **Last resort: `nsenter`** for true low-level work:
   ```bash
   nsenter -t $(docker inspect -f '{{.State.Pid}}' <id>) -n -p -m sh
   ```

## Common patterns

| Symptom | First check | Common cause |
|---------|-------------|--------------|
| "Up" but no traffic | `ss -ltn` inside | `127.0.0.1` instead of `0.0.0.0` |
| OOMKilled | `inspect.State.OOMKilled` | Wrong limit; missing GC; model too big |
| `Permission denied` writing to /data | `ls -ld /data` + `id` | volume owned by host UID; non-root container |
| EAGAIN / TooManyOpenFiles | `cat /proc/<pid>/limits` | `ulimit -n` too low |
| Hangs at startup | `strace -p <pid>` | Blocking DNS lookup; waiting on dead dependency |
