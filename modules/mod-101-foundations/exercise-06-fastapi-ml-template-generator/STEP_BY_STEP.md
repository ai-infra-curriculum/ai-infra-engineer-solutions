# Step-by-Step Implementation Guide: FastAPI ML Template Generator

This guide provides detailed instructions for implementing the FastAPI ML service template generator.

## Overview

The template generator creates production-ready FastAPI applications for ML model serving. It consists of:

1. **Template Engine**: Core logic for rendering Jinja2 templates
2. **Templates**: Jinja2 templates for all project files
3. **CLI**: Command-line interface for project generation
4. **Validators**: Configuration validation logic

## Key Components

### 1. Template Engine (`template_engine.py`)

The `TemplateEngine` class handles:
- Loading Jinja2 templates
- Rendering templates with context variables
- Formatting generated Python code
- Creating directory structures
- Validating configurations

### 2. Project Templates

Template types:
- **Image Classification**: Upload images, return predictions
- **Text Classification**: Analyze text, return categories
- **Object Detection**: Detect objects with bounding boxes
- **Time Series**: Predict future values
- **Generic**: Customizable template

### 3. Generated Files

For each project, the generator creates:
- FastAPI application with routes
- Pydantic models for validation
- ML model wrapper class
- Comprehensive test suite
- Docker configuration
- CI/CD pipelines
- Documentation

### 4. CLI Interface

Commands:
- `generate`: Create new project
- `list-templates`: Show available templates
- `validate`: Validate project configuration

## Implementation Steps

### Step 1: Template Engine

Create `src/mlapi_gen/template_engine.py`:

```python
class TemplateEngine:
    def __init__(self, templates_dir: Path):
        self.templates_dir = templates_dir
        self.env = Environment(loader=FileSystemLoader(templates_dir))

    def generate_project(self, config: ProjectConfig, output_dir: Path):
        # Create directory structure
        # Render templates
        # Format code
        pass
```

### Step 2: Create Jinja2 Templates

See `templates/` directory for examples.

### Step 3: CLI

Create `src/mlapi_gen/cli.py` with Click commands.

### Step 4: Testing

Test generated projects to ensure they:
- Build successfully
- Pass all tests
- Run without errors
- Have proper documentation

## Usage

```bash
# Generate project
mlapi-gen generate my-api --template image_classification

# With options
mlapi-gen generate my-api \
    --template generic \
    --with-auth \
    --with-monitoring

# Interactive mode
mlapi-gen generate my-api --interactive
```

## Testing Generated Projects

All generated projects include:
- Unit tests for endpoints
- Integration tests
- Mock fixtures
- Test fixtures for sample data

Run tests with:
```bash
pytest tests/ -v --cov=app
```

## Deployment

Generated projects include:
- Multi-stage Dockerfile
- docker-compose.yml
- GitHub Actions workflows
- Health check endpoints

Deploy with:
```bash
docker-compose up
```

## Extending Templates

To add a new template:
1. Create template files in `templates/`
2. Add template description to `TEMPLATES` dict
3. Create test cases
4. Update documentation
