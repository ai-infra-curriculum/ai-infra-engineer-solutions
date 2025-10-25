# Contributing to AI Infrastructure Engineer Solutions

First off, thank you for considering contributing to this project! It's people like you that make this curriculum valuable for learners worldwide.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Contribution Guidelines](#contribution-guidelines)
- [Style Guides](#style-guides)
- [Commit Messages](#commit-messages)
- [Pull Request Process](#pull-request-process)
- [Community](#community)

## 📜 Code of Conduct

This project adheres to a Code of Conduct that all contributors are expected to follow. Please read [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before contributing.

**In short:**
- Be respectful and inclusive
- Welcome newcomers and learners
- Focus on constructive feedback
- Assume good intentions
- Help create a positive learning environment

## 🤝 How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues to avoid duplicates.

**When reporting a bug, include:**

- **Clear title** - Descriptive and specific
- **Environment details** - OS, Python version, Docker version, Kubernetes version
- **Reproduction steps** - Step-by-step instructions
- **Expected behavior** - What should happen
- **Actual behavior** - What actually happens
- **Logs and errors** - Full error messages and relevant logs
- **Screenshots** - If applicable

**Example bug report:**

```markdown
## Bug: Airflow DAG fails with database connection error

**Environment:**
- OS: Ubuntu 22.04
- Python: 3.11.5
- Docker: 24.0.6
- Project: project-102-mlops-pipeline

**Steps to Reproduce:**
1. Run `docker-compose up -d`
2. Wait for containers to start
3. Access Airflow UI at localhost:8080
4. Trigger `ml_training_pipeline` DAG

**Expected:**
DAG runs successfully and trains model

**Actual:**
DAG fails with error: "Database connection refused"

**Logs:**
```
[paste relevant logs]
```

**Additional Context:**
Happens consistently on fresh setup, but works after manually restarting postgres container.
```

### Suggesting Enhancements

Enhancement suggestions are welcome! Please provide:

- **Clear use case** - Why is this valuable?
- **Detailed description** - What should be added/changed?
- **Examples** - How would it work?
- **Alternatives considered** - What other approaches were evaluated?

### Contributing Code

Code contributions are highly valued! Here are areas where contributions are especially welcome:

#### 🐛 Bug Fixes
- Fix issues in existing implementations
- Improve error handling
- Fix documentation errors

#### ✨ Enhancements
- Improve performance and optimization
- Add additional features
- Enhance monitoring and observability
- Improve user experience

#### 📚 Documentation
- Improve existing documentation
- Add missing documentation
- Create tutorials and guides
- Fix typos and clarify confusing sections

#### 🧪 Tests
- Add missing test cases
- Improve test coverage
- Add integration tests
- Add load/performance tests

#### 🚀 New Features
- Alternative implementations
- Additional deployment options
- New monitoring dashboards
- Additional optimizations

#### ☁️ Cloud Providers
- AWS-specific deployments
- GCP-specific deployments
- Azure-specific deployments
- Multi-cloud patterns

## 🛠️ Development Setup

### Prerequisites

- Python 3.11+
- Docker 24.0+
- Docker Compose
- kubectl (for Kubernetes testing)
- minikube or kind (for local Kubernetes)
- Git

### Fork and Clone

1. **Fork the repository** on GitHub

2. **Clone your fork:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/ai-infra-engineer-solutions.git
   cd ai-infra-engineer-solutions
   ```

3. **Add upstream remote:**
   ```bash
   git remote add upstream https://github.com/ai-infra-curriculum/ai-infra-engineer-solutions.git
   ```

4. **Create a development branch:**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

### Set Up Development Environment

For project-specific development:

```bash
# Navigate to the project
cd projects/project-101-basic-model-serving/

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # if available

# Install pre-commit hooks
pre-commit install  # if using pre-commit
```

### Running Tests

Before submitting changes, ensure all tests pass:

```bash
# Run unit tests
pytest tests/unit/ -v

# Run integration tests
pytest tests/integration/ -v

# Run all tests with coverage
pytest tests/ --cov=src --cov-report=html --cov-report=term

# Run linting
flake8 src/ tests/
black --check src/ tests/
mypy src/

# Run security checks
bandit -r src/
```

### Testing Locally

Test your changes in Docker and Kubernetes:

```bash
# Test with Docker Compose
docker-compose build
docker-compose up

# Run smoke tests
./scripts/test-deployment.sh

# Test in Kubernetes
minikube start
kubectl apply -f kubernetes/
kubectl get pods
```

## 📏 Contribution Guidelines

### General Principles

1. **Quality over quantity** - Well-tested, documented code is better than lots of features
2. **Educational value** - Remember this is a learning resource
3. **Production-ready** - Solutions should reflect real-world best practices
4. **Clear and documented** - Code should be easy to understand
5. **Tested** - All code should have appropriate tests

### Code Quality Standards

#### ✅ Do's

- **Write clear, readable code** - Others need to learn from it
- **Add comprehensive docstrings** - Explain purpose, parameters, returns
- **Include type hints** - Makes code more maintainable
- **Write tests** - Unit tests at minimum
- **Follow existing patterns** - Consistency is important
- **Add logging** - Appropriate INFO, DEBUG, ERROR logging
- **Handle errors gracefully** - Proper exception handling
- **Document complex logic** - Add comments for non-obvious code
- **Update documentation** - Keep docs in sync with code

#### ❌ Don'ts

- **Don't sacrifice clarity for cleverness** - Readable > clever
- **Don't commit sensitive data** - No keys, passwords, secrets
- **Don't break existing functionality** - Maintain backward compatibility
- **Don't skip tests** - Testing is not optional
- **Don't hardcode values** - Use configuration
- **Don't add unnecessary dependencies** - Keep it lean
- **Don't copy-paste without attribution** - Give credit where due

### Code Review Checklist

Before submitting PR, verify:

- [ ] Code follows project style guide
- [ ] All tests pass
- [ ] New functionality has tests
- [ ] Documentation is updated
- [ ] No sensitive data committed
- [ ] Commit messages follow guidelines
- [ ] Code is properly formatted
- [ ] Type hints are added
- [ ] Docstrings are comprehensive
- [ ] No linting errors
- [ ] Changes are atomic and focused
- [ ] PR description is clear

## 🎨 Style Guides

### Python Style Guide

Follow **PEP 8** with these specifics:

```python
# Line length: 100 characters (not 79)
# Use Black for formatting
# Use isort for import sorting

# Example function
def train_model(
    data: pd.DataFrame,
    config: TrainingConfig,
    model_name: str = "model_v1"
) -> Tuple[Model, Dict[str, float]]:
    """
    Train a machine learning model with given configuration.

    This function handles data preprocessing, model training,
    and validation. It returns both the trained model and
    training metrics.

    Args:
        data: Training data as pandas DataFrame
        config: Training configuration object
        model_name: Name for the trained model (default: "model_v1")

    Returns:
        Tuple containing:
        - Trained model object
        - Dictionary of training metrics (loss, accuracy, etc.)

    Raises:
        ValueError: If data is empty or invalid
        RuntimeError: If training fails

    Example:
        >>> config = TrainingConfig(epochs=10, lr=0.001)
        >>> model, metrics = train_model(df, config)
        >>> print(f"Accuracy: {metrics['accuracy']:.2%}")
    """
    # Implementation
    pass
```

### Documentation Style

**README files:**
- Start with clear title and description
- Include badges (license, version, etc.)
- Provide quick start instructions
- Include examples
- Link to detailed documentation
- Keep concise but comprehensive

**Code documentation:**
- Clear docstrings for all public functions/classes
- Inline comments for complex logic
- Architecture documentation for systems
- API documentation for endpoints

**Guides and tutorials:**
- Start with prerequisites
- Include step-by-step instructions
- Provide examples
- Explain the "why" not just the "how"
- Include troubleshooting section

### Kubernetes Manifests

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: model-server
  labels:
    app: model-server
    version: v1
    component: api
  annotations:
    description: "ML model serving API"
spec:
  replicas: 3
  selector:
    matchLabels:
      app: model-server
  template:
    metadata:
      labels:
        app: model-server
        version: v1
    spec:
      containers:
      - name: api
        image: model-server:latest
        ports:
        - containerPort: 8000
          name: http
        # ... rest of spec
```

### Docker Best Practices

```dockerfile
# Use specific base image versions
FROM python:3.11-slim AS base

# Set working directory
WORKDIR /app

# Copy requirements first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Use non-root user
RUN useradd -m -u 1000 appuser
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Command
CMD ["python", "src/main.py"]
```

## 💬 Commit Messages

Follow the **Conventional Commits** specification:

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks
- `perf`: Performance improvements
- `ci`: CI/CD changes

### Examples

```bash
# Feature
feat(project-01): add model versioning support

Implement A/B testing capability with model versioning.
Models can now be versioned and traffic can be split
between versions for testing.

Closes #123

# Bug fix
fix(project-02): resolve airflow database connection issue

Fix race condition where Airflow webserver starts before
PostgreSQL is ready. Added health check and retry logic.

Fixes #456

# Documentation
docs(project-03): add troubleshooting guide for GPU issues

Add comprehensive guide for debugging GPU-related problems
including CUDA errors, memory issues, and driver problems.

# Refactoring
refactor(project-01): extract metrics collection to separate module

Improve code organization by moving Prometheus metrics
collection to dedicated module. No functional changes.
```

## 🔄 Pull Request Process

### Before Submitting PR

1. **Update from upstream:**
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run all tests:**
   ```bash
   pytest tests/ -v
   ```

3. **Check code quality:**
   ```bash
   black src/ tests/
   flake8 src/ tests/
   mypy src/
   ```

4. **Update documentation:**
   - Update README if needed
   - Update CHANGELOG
   - Add/update docstrings

### PR Title and Description

**Title format:**
```
[TYPE] Brief description
```

**Description template:**
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix or feature that would break existing functionality)
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Code refactoring

## Changes Made
- Change 1
- Change 2
- Change 3

## Testing
Describe testing performed:
- Unit tests added/updated
- Integration tests pass
- Manual testing performed

## Screenshots (if applicable)
Add screenshots for UI changes

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review performed
- [ ] Code is commented (complex parts)
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tests added and passing
- [ ] No breaking changes (or documented)
- [ ] Commit messages follow guidelines

## Related Issues
Closes #123
Relates to #456
```

### Review Process

1. **Automated checks** run on PR submission
2. **Maintainer review** within 48-72 hours
3. **Address feedback** and push changes
4. **Approval** from at least one maintainer
5. **Merge** by maintainer

### After PR is Merged

1. **Delete your branch:**
   ```bash
   git branch -d feature/your-feature-name
   ```

2. **Update your fork:**
   ```bash
   git checkout main
   git pull upstream main
   git push origin main
   ```

## 🌟 Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Acknowledged in release notes
- Given credit in documentation

Significant contributions may lead to:
- Collaborator access
- Maintainer status
- Inclusion in project decisions

## 📞 Community

### Communication Channels

- **GitHub Issues** - Bug reports, feature requests
- **GitHub Discussions** - Questions, ideas, general discussion
- **Email** - ai-infra-curriculum@joshua-ferguson.com

### Getting Help

- Check existing documentation
- Search closed issues
- Ask in GitHub Discussions
- Email maintainers

## 🙏 Thank You

Every contribution, no matter how small, is valuable:
- Reporting bugs
- Suggesting features
- Fixing typos
- Improving documentation
- Writing code
- Reviewing PRs
- Helping other contributors

Thank you for helping make this curriculum better for everyone!

---

**Questions?** Open an issue or discussion, we're happy to help!
