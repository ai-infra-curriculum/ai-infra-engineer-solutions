"""Tests for Python version detection."""

import pytest
from pyenvman.python_detector import PythonDetector, PythonVersion
from pathlib import Path


def test_python_detector_initialization():
    """Test PythonDetector initialization."""
    detector = PythonDetector()
    assert detector is not None
    assert isinstance(detector.found_pythons, list)


def test_detect_all_finds_pythons():
    """Test that detect_all finds at least one Python."""
    detector = PythonDetector()
    pythons = detector.detect_all()
    assert len(pythons) > 0
    assert all(isinstance(p, PythonVersion) for p in pythons)


def test_python_version_has_required_fields():
    """Test PythonVersion dataclass has required fields."""
    detector = PythonDetector()
    pythons = detector.detect_all()
    if pythons:
        py = pythons[0]
        assert py.version
        assert py.path
        assert py.manager in ["system", "pyenv", "conda", "asdf"]


def test_version_tuple_parsing():
    """Test version tuple parsing."""
    assert PythonDetector._version_tuple("3.11.5") == (3, 11, 5)
    assert PythonDetector._version_tuple("3.10.0") == (3, 10, 0)
    assert PythonDetector._version_tuple("invalid") == (0, 0, 0)
