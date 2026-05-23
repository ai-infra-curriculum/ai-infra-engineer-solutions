# Bug 3: filesystem permission

## Symptom
Container exits with `PermissionError: [Errno 13] Permission denied: '/data/test.txt'`.

## Diagnosis path

1. `docker exec` (or `kubectl debug --target`) into the running container:
   ```sh
   id
   # uid=10001(app) gid=10001(app)
   ls -ld /data
   # drwxr-xr-x 2 root root 4096 ... /data
   ```
   `/data` is owned by root; container user is `app` (uid 10001) with no write perm.

2. Two common roots:
   - **Image issue**: `WORKDIR /data` creates the dir as root before the `USER` switch. Image must chown the dir.
   - **Volume issue**: a host-mounted volume keeps the host UID, regardless of image config.

## Fix
- **Image**: add `RUN chown -R app:app /data` BEFORE `USER app`.
- **K8s**: set `spec.securityContext.fsGroup: 10001` so the kubelet adjusts the mount.
- **docker compose**: prefer named volumes over bind mounts when UID mismatch is possible.

## Lesson
Non-root images need explicit filesystem ownership setup. The combination of `USER` + `WORKDIR <newdir>` is a frequent source of this bug.
