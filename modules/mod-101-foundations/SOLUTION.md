# SOLUTION — Foundations

> Read this *after* you have built the exercises yourself. This file
> explains the *why* behind the reference implementations — what we
> chose, what we ruled out, and what the common grader-observed
> mistakes are.

## What this module is really teaching

Foundations is the module everyone wants to skip. It's also the
module whose gaps produce the most expensive bugs downstream:

- Python environments that "work on my machine" but break in CI.
- Containers that build in 8 minutes locally and 40 in CI because
  the layer cache was never engineered.
- API templates that ship without observability hooks and only get
  them retrofitted three sprints later.

The reference solutions for ex-04 (pyenvman), ex-05 (ML framework
benchmark), and ex-06 (FastAPI ML template generator) all share a
common backbone: they are **opinionated CLIs** that bake the right
defaults into the tool itself, so engineers who use them inherit
the discipline.

## Architectural decisions and *why*

### Decision 1: Use ``pyenv`` + ``venv`` + ``pip-tools``, not Poetry or conda

Exercise 04 (pyenvman) builds on the trio above rather than wrapping
Poetry or conda. The reason: every ML team eventually has to
support both an internal package built with pip and an external
data scientist using conda. The trio works in both worlds; Poetry
and conda each force a stack choice that bites later.

**Anti-pattern to avoid**: hard-coding ``poetry`` or ``conda`` into
team tooling. The next team you onboard will use the other one and
you'll spend a quarter migrating.

### Decision 2: Benchmark in subprocesses, not in the calling process

Exercise 05 (ML framework benchmark) launches PyTorch, TensorFlow,
and JAX in **separate subprocesses**. The reason: import-time side
effects (CUDA init, oneDNN warmup) leak into the calling process
and contaminate later benchmarks. Subprocesses guarantee clean
state per framework.

This costs ~1 second of process startup per framework but produces
honest numbers. The alternative (importing all three in one
process) makes the second-imported framework look 2-5x slower than
it is.

### Decision 3: Template-based code generation with Jinja2

Exercise 06 (FastAPI ML template generator) uses Jinja2 templates
rather than string concatenation or AST manipulation. The reason:

- **String concatenation** invariably produces broken Python with
  missing newlines or wrong indentation in the corner cases.
- **AST manipulation** is the right tool for *modifying* existing
  code, not generating new code from scratch.
- **Jinja2** is the right balance for code generation — readable
  templates, escapable contexts, deterministic output.

The reference template includes Prometheus instrumentation,
structured logging, OpenAPI metadata, and graceful shutdown by
default. Engineers who use the generator inherit these without
thinking about them.

### Decision 4: Health endpoints separated into liveness + readiness

The generated FastAPI template exposes ``/health/live`` and
``/health/ready`` as separate endpoints even for tiny services.
The reason: Kubernetes' liveness and readiness probes have
different semantics (restart vs. drain), and conflating them in
one ``/health`` endpoint breaks both behaviors when the service
grows.

The cost: two endpoints instead of one. The benefit: correct
behavior under K8s rolling updates from day one.

## Trade-offs we deliberately accepted

### CPU-first inference benchmarks

The benchmark tool ships with CPU-first defaults. GPU benchmarks
are available behind a flag but aren't the default. The reason:
CPU benchmarks reproduce identically across laptops, CI runners,
and cloud VMs; GPU benchmarks depend on driver versions, CUDA
versions, and specific hardware. CPU numbers are honest;
"my-laptop-vs-yours" GPU numbers are usually misleading.

### Single-process FastAPI default

The template generator emits a single-worker FastAPI app. For
production, it's expected to run under ``uvicorn --workers N`` or
behind Gunicorn. We make this an explicit deployment-time choice
rather than baking it into the template.

### English-only error messages

The template's error messages are English. i18n is a real concern
for some teams but adds enough complexity that it's better
introduced when needed rather than built into a foundation tool.

## Common mistakes graders see

1. **Hardcoding paths**: ``/Users/alice/projects`` makes it into
   the template repo. Use ``pathlib`` and resolve at runtime.
2. **Activating a venv inside the tool**: ``venv activate`` is a
   shell built-in; tools should *invoke* the venv's Python
   directly via ``venv/bin/python``.
3. **Subprocess without ``check=True``**: silent command failures
   produce confusing downstream errors. Always check.
4. **Comparing benchmark results without warmup**: the first run
   pays JIT / lazy-loading costs. Always discard.
5. **Generating Python without ``black``-formatting the output**:
   the generated code is the user's first impression. Run ``black``
   on the result.
6. **Forgetting the Dockerfile in the template**: a "production
   ready" FastAPI scaffold without a Dockerfile leaves the user
   stranded the moment they want to deploy.

## When to go beyond this implementation

- Add a **pipx** distribution channel for ``pyenvman`` so the tool
  can be installed independently of any project's Python.
- Extend the benchmark tool to **report Memory Bandwidth Usage**
  (MBU) and **Arithmetic Intensity**, not just throughput.
- Generate **OpenTelemetry tracing** as part of the FastAPI
  template — modern observability needs traces, not just metrics.

## Related curriculum touchpoints

- ``engineer/mod-103-containerization`` — packaging the tools you
  built here.
- ``engineer/mod-108-monitoring-observability`` — the
  observability hooks the template embeds.
- ``performance/mod-001-gpu-fundamentals`` — the right metrics for
  the GPU-aware benchmark.
- ``junior-engineer/project-01-simple-model-api`` — the user-facing
  application that uses these foundations.
