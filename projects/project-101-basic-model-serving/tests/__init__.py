"""
Test suite for model serving system.

This package contains comprehensive tests for the model serving system,
including API tests, model loading tests, and utility function tests.

Test Modules:
    - test_api: FastAPI endpoint tests
    - test_model: Model loading and inference tests
    - test_utils: Utility function tests
    - conftest: Pytest fixtures and configuration

Usage:
    Run all tests:
        pytest tests/

    Run specific test module:
        pytest tests/test_api.py

    Run with coverage:
        pytest tests/ --cov=src --cov-report=html

    Run with markers:
        pytest tests/ -m "not slow"
"""

__all__ = []
