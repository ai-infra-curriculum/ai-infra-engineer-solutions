"""Pytest configuration and fixtures."""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import tempfile
import shutil

@pytest.fixture
def sample_data():
    """Generate sample churn data for testing."""
    np.random.seed(42)
    n_samples = 1000

    data = {
        'tenure': np.random.randint(0, 72, n_samples),
        'monthly_charges': np.random.uniform(20, 120, n_samples),
        'total_charges': np.random.uniform(100, 8000, n_samples),
        'contract_type': np.random.choice(['Month-to-month', 'One year', 'Two year'], n_samples),
        'payment_method': np.random.choice(['Electronic check', 'Mailed check', 'Bank transfer', 'Credit card'], n_samples),
        'internet_service': np.random.choice(['DSL', 'Fiber optic', 'No'], n_samples),
        'online_security': np.random.uniform(-1, 1, n_samples),
        'tech_support': np.random.uniform(-1, 1, n_samples),
        'streaming_tv': np.random.uniform(-1, 1, n_samples),
        'streaming_movies': np.random.uniform(-1, 1, n_samples),
        'paperless_billing': np.random.uniform(-1, 1, n_samples),
        'senior_citizen': np.random.uniform(-1, 1, n_samples),
        'partner': np.random.uniform(-1, 1, n_samples),
        'dependents': np.random.uniform(-1, 1, n_samples),
        'multiple_lines': np.random.uniform(-1, 1, n_samples),
        'Churn': np.random.choice([0, 1], n_samples, p=[0.7, 0.3])
    }

    return pd.DataFrame(data)


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def sample_model():
    """Create a simple trained model for testing."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.datasets import make_classification

    X, y = make_classification(n_samples=100, n_features=10, random_state=42)
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    model.fit(X, y)

    return model


@pytest.fixture
def mock_mlflow(monkeypatch):
    """Mock MLflow for testing."""
    class MockRun:
        def __init__(self):
            self.info = type('obj', (object,), {'run_id': 'test_run_id'})

    class MockMLflow:
        @staticmethod
        def set_tracking_uri(uri):
            pass

        @staticmethod
        def set_experiment(name):
            pass

        @staticmethod
        def start_run(*args, **kwargs):
            return MockRun()

        @staticmethod
        def log_param(*args, **kwargs):
            pass

        @staticmethod
        def log_metric(*args, **kwargs):
            pass

        @staticmethod
        def log_params(*args, **kwargs):
            pass

        @staticmethod
        def log_metrics(*args, **kwargs):
            pass

        @staticmethod
        def log_text(*args, **kwargs):
            pass

        class sklearn:
            @staticmethod
            def log_model(*args, **kwargs):
                pass

    return MockMLflow()
