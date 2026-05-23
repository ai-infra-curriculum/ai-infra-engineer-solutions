# Bug 1: bind address

## Symptom
`docker run -d -p 8000:8000 bug-1` returns a container ID. `curl localhost:8000` → connection refused. Logs say "Application startup complete".

## Diagnosis path

1. `docker logs` shows app started → not a crash.
2. `docker exec -it <id> sh` → inside the container:
   ```sh
   apk add iproute2 || apt-get install iproute2
   ss -ltn
   # LISTEN 0 5 127.0.0.1:8000 0.0.0.0:*
   ```
   That `127.0.0.1` is the smoking gun. The app is only listening on the container's loopback — the host port-publish has nothing to forward to.

3. `Dockerfile.broken` has `--host 127.0.0.1`. Change to `0.0.0.0`.

## Lesson
"Up" doesn't mean "reachable". Always confirm with `ss -ltn` what address the app is actually bound to.
