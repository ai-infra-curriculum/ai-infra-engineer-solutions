# SOLUTION — Containerization

> Read this *after* you have built the containers yourself. This
> document explains *why* the reference Dockerfiles are shaped the
> way they are: layer ordering, multi-stage builds, security
> postures, and the small choices that make CI builds 5x faster.

## What this module is really teaching

Containers are deceptively simple. Anyone can write a working
Dockerfile in 20 minutes. Writing one that:

1. builds in under 60 seconds on cold cache,
2. ships under 200 MB,
3. runs as a non-root user,
4. handles SIGTERM correctly,
5. caches dependency layers properly,

is a different skill, and it's the skill that distinguishes ML
infrastructure engineers from "people who use containers."

## Architectural decisions and *why*

### Decision 1: Multi-stage builds, always

Every reference Dockerfile uses multi-stage builds. The pattern:

```dockerfile
FROM python:3.11-slim AS builder
RUN apt-get update && apt-get install -y build-essential
COPY requirements.txt .
RUN pip wheel --wheel-dir /wheels -r requirements.txt

FROM python:3.11-slim AS runtime
COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels --no-cache-dir <pkgs>
```

The reason: the runtime image carries only the wheels, not the
build toolchain. Image size drops 3-5x; the attack surface drops
along with it.

**Anti-pattern to avoid**: ``apt-get install build-essential`` in
the runtime image. Now your prod container ships GCC.

### Decision 2: Dependency layers ordered by change frequency

Reference Dockerfiles install dependencies in a strict order:

1. System packages (rarely change).
2. ``requirements.txt`` (changes occasionally).
3. Source code (changes constantly).

This ordering is the single biggest determinant of build cache hit
rate. Out-of-order Dockerfiles invalidate caches on every code
change and turn 30-second builds into 5-minute builds.

### Decision 3: ``USER`` non-root in every container

Every reference Dockerfile ends with:

```dockerfile
RUN useradd --create-home --shell /bin/bash appuser
USER appuser
```

The reason: running as root inside the container is the most-
common way containers contribute to a security incident. Many K8s
clusters enforce ``runAsNonRoot``; ships that haven't done this
work fail to schedule.

### Decision 4: Distroless / scratch for the leanest images

When the workload tolerates it (Go static binaries, Python with
``pip install``-only deps), the reference solutions use distroless
or scratch as the runtime base. Image sizes drop to 20-80 MB and
the CVE surface shrinks dramatically.

The trade-off: no shell, no ``apt``, no debugging in the container
itself. Engineers have to be comfortable with ``kubectl debug`` or
ephemeral debug containers.

### Decision 5: ``HEALTHCHECK`` defined in the Dockerfile

The reference Dockerfiles include:

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8080/health || exit 1
```

Docker's ``HEALTHCHECK`` is the local equivalent of K8s' readiness
probe. Including it means ``docker ps`` shows healthy/unhealthy
status, and ``docker compose`` can wait for dependencies properly.

## Trade-offs we deliberately accepted

### No image vulnerability scanning in the Dockerfile

Scanning (Trivy, Snyk, Grype) is a CI concern, not a Dockerfile
concern. The reference solutions wire scanning into the CI
workflow, not into ``docker build`` itself. The reason: scans
take 30-90 seconds and shouldn't gate local development.

### Per-language base image picks

We pick distinct base images per language family:

- Python: ``python:3.11-slim`` (Debian-based, smallest with pip).
- Go: ``gcr.io/distroless/static-debian12`` (smallest workable).
- Node: ``node:20-bookworm-slim``.
- Generic shell: ``debian:12-slim``.

A monoculture (everything on Alpine, or everything on Ubuntu) is
tempting but causes subtle bugs (musl vs glibc surprises in
Python's compiled wheels, for example).

### English locale baked in

The reference images set ``LANG=C.UTF-8``. Other locales are
possible but expand the image and surface charset-encoding bugs.

## Common mistakes graders see

1. **Source code copied before dependencies**: ``COPY . .``
   followed by ``RUN pip install`` invalidates the dep cache on
   every code change.
2. **Latest tags in production**: ``python:latest`` ships
   surprise breaking changes. Always pin the version.
3. **``COPY .`` without ``.dockerignore``**: ships ``.git``, IDE
   configs, secrets, virtualenvs. Always add ``.dockerignore``.
4. **Running ``apt-get`` without ``--no-install-recommends``**:
   pulls in surprise dependencies that bloat the image.
5. **``ENTRYPOINT`` vs ``CMD`` confusion**: pick ``ENTRYPOINT
   ["python", "-u"]`` ``CMD ["main.py"]`` for the right behavior.
6. **No SIGTERM handling in the entrypoint**: Python apps default
   to ignoring SIGTERM. Wrap in ``exec`` or handle the signal.

## When to go beyond this implementation

- Add **container provenance** (SLSA attestations) signed via
  ``cosign``.
- Move to **buildkit**-native cache mounts for pip / apt / go
  module caches — another 2-3x build speedup.
- Adopt **Chainguard images** for further-reduced CVE surface.

## Related curriculum touchpoints

- ``engineer/mod-104-kubernetes`` — where these containers run.
- ``engineer/mod-109-infrastructure-as-code`` — building images
  as part of the deploy pipeline.
- ``junior-engineer/project-02-kubernetes-serving`` — the user-
  facing app that uses the container patterns here.
- ``performance/mod-007-production-deployment`` — production
  rollout of containerized services.
