"""Pytest configuration and fixtures."""

import pytest
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def sample_requirements(temp_dir):
    """Create sample requirements.txt file."""
    req_file = temp_dir / "requirements.txt"
    req_file.write_text("""
click>=8.1.0
rich>=13.0.0
requests>=2.31.0
""")
    return req_file
