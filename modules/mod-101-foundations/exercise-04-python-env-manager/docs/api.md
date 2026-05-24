# `pyenvman` — CLI API Reference

Command-line tool for managing Python versions, virtual environments, dependencies, and project scaffolding. Implemented in `src/pyenvman/cli.py` using `click` for argument parsing and `rich` for terminal output.

This document is the authoritative reference. When help text in the binary and this document disagree, the binary wins — please file a docs PR.

## Synopsis

```text
pyenvman [GLOBAL_OPTIONS] COMMAND [COMMAND_OPTIONS] [ARGS]...
```

## Global options

| Flag | Purpose |
|---|---|
| `--version` | Print version and exit. |
| `--help` | Print help and exit. Works at every level: `pyenvman --help`, `pyenvman venv --help`, `pyenvman venv create --help`. |

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `PYENVMAN_HOME` | `~/.pyenvman` | Root for managed venvs and cached metadata. |
| `PYENVMAN_VENV_DIR` | `$PYENVMAN_HOME/venvs` | Where `venv create` stores environments. |
| `PYENVMAN_REGISTRY_URL` | unset | Optional PyPI mirror used by `deps check`, `deps lock`, and `deps audit`. |
| `PYENVMAN_NO_COLOR` | unset | Set to disable rich coloring (for CI logs). Equivalent to `NO_COLOR=1`. |
| `PYENVMAN_LOG_LEVEL` | `INFO` | One of `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `PYENVMAN_AUDIT_DB` | (PyPI advisory DB) | Override the vulnerability DB path for `deps audit`. |

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success. |
| `1` | Generic runtime error (the most common; check stderr for the message). |
| `2` | Bad usage — missing flag, unknown subcommand, conflicting options. Emitted by `click` itself. |
| `3` | Dependency conflict found (`deps check`). |
| `4` | Security audit found vulnerabilities (`deps audit`). |
| `5` | Resource not found — e.g., venv name doesn't exist for `venv delete`. |
| `6` | Permission denied — usually trying to write into a system Python's site-packages. |
| `130` | Interrupted (Ctrl-C). |

When scripting, prefer matching specific exit codes over parsing stdout.

---

## Top-level groups

```
pyenvman
├── python      Manage Python interpreters
├── venv        Manage virtual environments
├── deps        Manage dependencies
└── project     Initialize projects
```

---

## `pyenvman python`

Manage Python interpreters detected on the host.

### `python list`

```text
pyenvman python list
```

List every Python interpreter pyenvman can detect on this host. Sources scanned:

1. `PATH` — every `python`, `python3`, `python3.x` binary.
2. `pyenv` — versions under `~/.pyenv/versions/`.
3. Common system locations — `/usr/bin`, `/usr/local/bin`, `/opt/homebrew/bin`, `/Library/Frameworks/Python.framework`.
4. Conda installations rooted at `~/miniconda3`, `~/anaconda3`, `~/mambaforge`.

**Options**: none.

**Output** (a rich table):

```text
                       Python Installations
┏━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃  Version  ┃  Path                            ┃  Manager ┃
┡━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━┩
│  3.12.6   │  /Users/me/.pyenv/versions/3.12.6│  pyenv   │
│  3.11.9   │  /Users/me/.pyenv/versions/3.11.9│  pyenv   │
│  3.11.7   │  /opt/homebrew/bin/python3.11    │  brew    │
│  3.9.6    │  /usr/bin/python3.9              │  system  │
└───────────┴──────────────────────────────────┴──────────┘

Total: 4 Python installations found
```

**Examples**

```bash
pyenvman python list
pyenvman python list --help     # show this command's help
```

---

## `pyenvman venv`

Create, list, clone, and delete managed virtual environments.

Managed venvs live under `$PYENVMAN_VENV_DIR` and are named — you reference them by name, not path. To use a plain ad-hoc venv inside a project directory, just use `python -m venv .venv` — pyenvman is not in the path of every project.

### `venv create`

```text
pyenvman venv create NAME [--python VERSION] [--requirements PATH]
```

Create a new managed virtual environment named `NAME`.

**Arguments**

- `NAME` — required. Identifier for the venv. Must be unique. Permitted chars: `[a-zA-Z0-9_-]`. Max 40 chars.

**Options**

| Flag | Default | Purpose |
|---|---|---|
| `-p, --python VERSION` | (currently active python) | Python version to use. Accepts either an exact version (`3.11.9`) or a major.minor (`3.11`, picks the highest detected patch). |
| `-r, --requirements PATH` | unset | After creating the venv, install from this `requirements.txt`. Must exist. |

**Errors**

- Exit 1 if `NAME` already exists.
- Exit 1 if `--python` is requested but no matching interpreter is detected.
- Exit 2 if `NAME` contains invalid characters.
- Exit 1 if `-r` install fails (the venv is left in place for inspection; delete with `venv delete`).

**Examples**

```bash
pyenvman venv create ml-project --python 3.11
pyenvman venv create api-service -p 3.12 -r requirements.txt
pyenvman venv create scratch                          # default python
```

**Output**

```text
✓ Virtual environment created at: /Users/me/.pyenvman/venvs/ml-project

To activate:
  source /Users/me/.pyenvman/venvs/ml-project/bin/activate
```

### `venv list`

```text
pyenvman venv list
```

List every managed venv, showing Python version, creation time, and on-disk size.

**Options**: none.

**Output**:

```text
                       Virtual Environments
┏━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┓
┃ Name         ┃ Python   ┃ Created             ┃   Size ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━┩
│ ml-project   │ 3.11.9   │ 2026-05-20T14:11:03Z│ 412 MB │
│ api-service  │ 3.12.6   │ 2026-05-22T09:04:55Z│ 287 MB │
└──────────────┴──────────┴─────────────────────┴────────┘

Total: 2 virtual environments
```

### `venv clone` _(planned for v0.2)_

```text
pyenvman venv clone SOURCE TARGET
```

Clone an existing venv to a new name. Copies the directory and rewrites shebangs to point at the new path.

> Status: declared in the README as a feature but not yet implemented in `cli.py` as of v0.1.0. Implementation lives behind `--experimental`. See the `STEP_BY_STEP.md` Step 4 to ship it.

### `venv delete`

```text
pyenvman venv delete NAME [--yes]
```

Delete a managed venv.

**Arguments**

- `NAME` — required.

**Options**

| Flag | Default | Purpose |
|---|---|---|
| `-y, --yes` | `false` | Skip the interactive confirmation prompt. Use in scripts. |

**Errors**

- Exit 1 if `NAME` doesn't exist.

**Examples**

```bash
pyenvman venv delete ml-project
pyenvman venv delete tmp-test --yes
```

---

## `pyenvman deps`

Analyze dependency files.

All `deps` subcommands take a single positional argument: the path to a `requirements.txt`. They do not yet support `pyproject.toml` parsing — that's planned for v0.3.

### `deps check`

```text
pyenvman deps check REQUIREMENTS [--python VERSION]
```

Detect dependency conflicts in a `requirements.txt` against a chosen Python version. Conflicts mean two or more packages pin the same transitive dependency to mutually exclusive versions.

**Options**

| Flag | Default | Purpose |
|---|---|---|
| `-p, --python VERSION` | `3.11` | Python version to resolve against (affects available wheel sets). |

**Output**: nothing if clean. Otherwise, a list of conflicts:

```text
✗ Found 2 conflicts:

Package: pydantic
  Required by: fastapi==0.110.0, langchain==0.1.0
  Conflicting versions: >=2.4,<3.0, >=1.0,<2.0
  Suggestion: Pin pydantic==2.6.0, upgrade langchain to 0.2+

Package: httpx
  Required by: openai==1.10.0, anthropic==0.18.0
  Conflicting versions: >=0.25,<1.0, >=0.23,<0.27
  Suggestion: Pin httpx==0.25.2
```

**Exit codes**

- `0` clean.
- `3` conflicts found.

**Examples**

```bash
pyenvman deps check requirements.txt
pyenvman deps check requirements.txt --python 3.12
echo $?    # 0 or 3
```

### `deps lock` _(planned for v0.2)_

```text
pyenvman deps lock REQUIREMENTS [--output PATH] [--python VERSION]
```

Generate a fully pinned lockfile (`requirements.lock`) by resolving the dependency tree to exact versions, including transitive dependencies and their hashes. Conceptually the same as `pip-compile`; we wrap it for consistency.

**Options**

| Flag | Default | Purpose |
|---|---|---|
| `-o, --output PATH` | `requirements.lock` | Output path. |
| `-p, --python VERSION` | `3.11` | Python version to lock for. |
| `--no-hashes` | `false` | Omit `--hash` entries (smaller diffs; sacrifices supply-chain protection). |

### `deps audit` _(planned for v0.2)_

```text
pyenvman deps audit REQUIREMENTS [--severity LEVEL]
```

Check declared and resolved dependencies against the PyPI Advisory Database (or the DB at `$PYENVMAN_AUDIT_DB`).

**Options**

| Flag | Default | Purpose |
|---|---|---|
| `--severity LEVEL` | `low` | Minimum severity to report: `low`, `medium`, `high`, `critical`. |
| `--json` | `false` | Emit machine-readable JSON instead of the rich table. |

**Exit codes**

- `0` no vulnerabilities at or above severity.
- `4` vulnerabilities found.

---

## `pyenvman project`

### `project init`

```text
pyenvman project init PATH [--template TEMPLATE] [--name NAME] [--python VERSION]
```

Scaffold a new project at `PATH` from a template. Creates the directory, a managed venv linked to the project (named `<project>-venv`), and the template's file layout.

**Arguments**

- `PATH` — required. Target directory. Created if missing. Refuses to overwrite non-empty existing dirs unless you delete first.

**Options**

| Flag | Default | Purpose |
|---|---|---|
| `-t, --template TEMPLATE` | `basic` | One of `basic`, `fastapi`, `ml`, `cli`. |
| `-n, --name NAME` | basename of `PATH` | Project name used in package metadata and README. |
| `-p, --python VERSION` | `3.11` | Python version for the project's venv. |

### Templates

| Template | What you get |
|---|---|
| `basic` | `src/<name>/__init__.py`, `tests/test_smoke.py`, `pyproject.toml` (PEP 621), README, MIT LICENSE, `.gitignore`. |
| `fastapi` | `basic` plus `src/<name>/api/main.py` (skeleton FastAPI app with `/health`), `tests/test_api.py` (httpx + pytest), `Dockerfile`, `docker-compose.yml`, requirements pinning fastapi + uvicorn + pydantic v2. |
| `ml` | `basic` plus `src/<name>/train.py`, `src/<name>/predict.py`, `notebooks/01-explore.ipynb`, `data/.gitkeep`, requirements pinning torch + numpy + pandas + scikit-learn + mlflow. |
| `cli` | `basic` plus `src/<name>/cli.py` (click skeleton), `pyproject.toml` with a `[project.scripts]` entry point, integration test that invokes the binary via `subprocess`. |

**Examples**

```bash
pyenvman project init ./my-api --template fastapi --python 3.11
pyenvman project init ./experiment --template ml --name yolo-train
pyenvman project init ./toolkit --template cli
```

**Output**

```text
✓ Project initialized at: my-api

Next steps:
  cd my-api
  source venv/bin/activate
  pytest tests/
```

---

## Programmatic API

`pyenvman` also exposes a Python API for use in scripts and tests. Public entry points:

```python
from pyenvman.python_detector import PythonDetector, PythonInfo
from pyenvman.venv_manager import VenvManager
from pyenvman.dependency_resolver import DependencyResolver, Conflict
from pyenvman.project_init import ProjectInitializer
```

Example:

```python
from pyenvman.venv_manager import VenvManager

mgr = VenvManager()
venv_path = mgr.create("my-env", python="3.11", requirements_path=None)
print(mgr.activate_script("my-env"))
```

The CLI is a thin wrapper; everything reachable from the CLI is reachable from these classes. See module docstrings for full signatures.

---

## Examples — end-to-end

```bash
# Set up a fresh ML project
pyenvman python list
pyenvman project init ~/code/yolo --template ml --python 3.11
cd ~/code/yolo
source venv/bin/activate

# Verify and add deps
pyenvman deps check requirements.txt --python 3.11
echo "ultralytics==8.1.0" >> requirements.txt
pyenvman deps check requirements.txt --python 3.11

# Iterate
pytest -q
```

```bash
# Scripted CI use
set -e
pyenvman venv create ci-build --python 3.11 --requirements requirements.txt
. "$PYENVMAN_VENV_DIR/ci-build/bin/activate"
pyenvman deps check requirements.txt
pytest
pyenvman venv delete ci-build --yes
```

---

## Versioning

Currently `0.1.0`. The CLI surface follows SemVer:

- **Patch (0.1.x)**: bug fixes, internal refactors, new examples.
- **Minor (0.x.0)**: new commands, new flags. Old flags continue to work.
- **Major (x.0.0)**: breaking changes to existing commands or flags.

Until 1.0, breaking changes may happen on minor bumps — see `CHANGELOG.md`.

---

## Reporting issues

When reporting a bug, include:

- `pyenvman --version`
- `python --version`
- Operating system and version
- The exact command and its full stderr (run with `PYENVMAN_LOG_LEVEL=DEBUG`)

If the bug involves a specific `requirements.txt`, include the minimal version of that file that reproduces the issue.
