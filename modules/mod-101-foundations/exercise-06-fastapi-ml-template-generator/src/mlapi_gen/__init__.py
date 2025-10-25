"""
mlapi-gen - FastAPI ML Service Template Generator

Generate production-ready FastAPI applications for ML model serving.
"""

__version__ = "0.1.0"
__author__ = "AI Infrastructure Engineer"

from .template_engine import TemplateEngine, ProjectConfig

__all__ = ["TemplateEngine", "ProjectConfig"]
