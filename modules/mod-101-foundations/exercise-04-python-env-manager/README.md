# Exercise 04: Python Environment Manager (pyenvman)

A comprehensive Python environment management tool that handles multiple Python versions, virtual environments, dependency resolution, and project scaffolding.

## Features

- **Python Version Management**: Detect and manage multiple Python installations
- **Virtual Environment Automation**: Create, clone, and manage virtual environments
- **Dependency Conflict Resolution**: Detect conflicts and suggest resolutions
- **Project Scaffolding**: Initialize projects with templates (basic, FastAPI, ML, CLI)
- **Security Auditing**: Check dependencies for known vulnerabilities
- **Lockfile Generation**: Create reproducible dependency specifications

## Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Install package in development mode
pip install -e .
```

### Basic Usage

```bash
# List all Python versions
pyenvman python list

# Create virtual environment
pyenvman venv create myproject --python 3.11

# Check dependencies for conflicts
pyenvman deps check requirements.txt

# Initialize new project
pyenvman project init ./myapp --template fastapi
```

## Project Structure

```
exercise-04-python-env-manager/
├── src/
│   ├── pyenvman/
│   │   ├── __init__.py
│   │   ├── python_detector.py      # Python version detection
│   │   ├── venv_manager.py         # Virtual environment management
│   │   ├── dependency_resolver.py  # Dependency conflict resolution
│   │   ├── project_init.py         # Project scaffolding
│   │   └── cli.py                  # Command-line interface
├── tests/
│   ├── test_python_detector.py
│   ├── test_venv_manager.py
│   ├── test_dependency_resolver.py
│   ├── test_project_init.py
│   └── test_cli.py
├── scripts/
│   ├── setup.sh
│   ├── run.sh
│   └── test.sh
├── README.md
├── STEP_BY_STEP.md
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
└── .gitignore
```

## Documentation

- [STEP_BY_STEP.md](STEP_BY_STEP.md) - Detailed implementation guide
- [API Documentation](docs/api.md) - API reference

## Testing

```bash
# Run all tests
./scripts/test.sh

# Run with coverage
pytest tests/ --cov=src/pyenvman --cov-report=html

# Run specific test file
pytest tests/test_venv_manager.py -v
```

## Examples

### Manage Python Versions

```bash
# List all Python versions
pyenvman python list

# Output:
# ┏━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┓
# ┃ Version ┃ Path                 ┃ Manager┃
# ┣━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━╋━━━━━━━━┫
# ┃ 3.11.5  ┃ /usr/bin/python3.11  ┃ system ┃
# ┃ 3.10.12 ┃ /usr/bin/python3.10  ┃ system ┃
# ┗━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━┻━━━━━━━━┛
```

### Virtual Environments

```bash
# Create venv with specific Python version
pyenvman venv create ml-project --python 3.11 --requirements requirements.txt

# List all venvs
pyenvman venv list

# Clone existing venv
pyenvman venv clone ml-project ml-project-test

# Delete venv
pyenvman venv delete ml-project-test
```

### Dependency Management

```bash
# Check for conflicts
pyenvman deps check requirements.txt --python 3.11

# Generate lockfile
pyenvman deps lock requirements.txt --output requirements.lock --python 3.11

# Security audit
pyenvman deps audit requirements.txt
```

### Project Initialization

```bash
# Create FastAPI project
pyenvman project init ./my-api --template fastapi --python 3.11

# Create ML project
pyenvman project init ./ml-experiment --template ml --python 3.11

# Create basic Python project
pyenvman project init ./basic-app --template basic
```

## Requirements

- Python 3.11+
- pip 23.0+
- git (for project initialization)

## License

MIT License - see LICENSE file for details
