"""
pyenvman - Advanced Python Environment Manager

A comprehensive tool for managing Python versions, virtual environments,
dependencies, and project scaffolding.
"""

__version__ = "0.1.0"
__author__ = "AI Infrastructure Engineer"

from .python_detector import PythonDetector, PythonVersion
from .venv_manager import VenvManager
from .dependency_resolver import DependencyResolver, Conflict, PackageInfo
from .project_init import ProjectInitializer

__all__ = [
    "PythonDetector",
    "PythonVersion",
    "VenvManager",
    "DependencyResolver",
    "Conflict",
    "PackageInfo",
    "ProjectInitializer",
]
