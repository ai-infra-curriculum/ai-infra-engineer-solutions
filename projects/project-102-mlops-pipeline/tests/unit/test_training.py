"""Unit tests for training module."""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, '/opt/airflow')

from src.training.trainer import ModelTrainer
from src.training.evaluator import ModelEvaluator


class TestModelTrainer:
    """Test ModelTrainer class."""

    def test_initialization(self, monkeypatch, temp_dir):
        """Test ModelTrainer initialization."""
        monkeypatch.setenv('MODELS_DIR', str(temp_dir))
        monkeypatch.setenv('MLFLOW_TRACKING_URI', 'http://localhost:5000')

        with patch('mlflow.set_tracking_uri'), patch('mlflow.set_experiment'):
            trainer = ModelTrainer()
            assert trainer.models_dir.exists()

    def test_get_model_configs(self, monkeypatch, temp_dir):
        """Test getting model configurations."""
        monkeypatch.setenv('MODELS_DIR', str(temp_dir))

        with patch('mlflow.set_tracking_uri'), patch('mlflow.set_experiment'):
            trainer = ModelTrainer()
            configs = trainer.get_model_configs()

            assert isinstance(configs, dict)
            assert 'logistic_regression' in configs
            assert 'random_forest' in configs
            assert 'xgboost' in configs

    def test_train_model(self, monkeypatch, temp_dir, sample_data):
        """Test training a single model."""
        monkeypatch.setenv('MODELS_DIR', str(temp_dir))

        with patch('mlflow.set_tracking_uri'), \
             patch('mlflow.set_experiment'), \
             patch('mlflow.start_run') as mock_run, \
             patch('mlflow.log_params'), \
             patch('mlflow.log_param'), \
             patch('mlflow.log_metric'), \
             patch('mlflow.log_metrics'), \
             patch('mlflow.log_text'), \
             patch('mlflow.sklearn.log_model'):

            # Setup mock
            mock_run.return_value.__enter__ = MagicMock(
                return_value=type('obj', (object,), {
                    'info': type('obj', (object,), {'run_id': 'test_run_id'})
                })()
            )
            mock_run.return_value.__exit__ = MagicMock(return_value=False)

            trainer = ModelTrainer()

            # Prepare data
            X = sample_data.drop(columns=['Churn'])
            y = sample_data['Churn']

            from sklearn.model_selection import train_test_split
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

            # Convert categorical to numeric for training
            for col in X_train.select_dtypes(include=['object']).columns:
                X_train[col] = pd.Categorical(X_train[col]).codes
                X_test[col] = pd.Categorical(X_test[col]).codes

            # Train model
            model, run_id = trainer.train_model(
                'logistic_regression',
                X_train, y_train,
                X_test, y_test
            )

            assert model is not None
            assert run_id == 'test_run_id'


class TestModelEvaluator:
    """Test ModelEvaluator class."""

    def test_initialization(self, monkeypatch, temp_dir):
        """Test ModelEvaluator initialization."""
        monkeypatch.setenv('MODELS_DIR', str(temp_dir))

        evaluator = ModelEvaluator()
        assert evaluator.models_dir.exists()

    def test_evaluate_model(self, sample_model, sample_data):
        """Test model evaluation."""
        evaluator = ModelEvaluator()

        # Prepare data
        from sklearn.datasets import make_classification
        X, y = make_classification(n_samples=100, n_features=10, random_state=42)

        metrics = evaluator.evaluate_model(sample_model, X, y)

        assert 'accuracy' in metrics
        assert 'precision' in metrics
        assert 'recall' in metrics
        assert 'f1_score' in metrics
        assert 'roc_auc' in metrics

        # Check metric ranges
        for metric, value in metrics.items():
            assert 0 <= value <= 1

    def test_check_model_thresholds(self, monkeypatch):
        """Test threshold checking."""
        monkeypatch.setenv('MIN_ACCURACY', '0.75')
        monkeypatch.setenv('MIN_PRECISION', '0.70')
        monkeypatch.setenv('MIN_RECALL', '0.70')
        monkeypatch.setenv('MIN_F1_SCORE', '0.70')

        from src.common.config import Config
        config = Config()

        evaluator = ModelEvaluator()

        # Metrics that meet thresholds
        good_metrics = {
            'accuracy': 0.80,
            'precision': 0.75,
            'recall': 0.75,
            'f1_score': 0.75
        }

        meets, failed = evaluator.check_model_thresholds(good_metrics)
        assert meets
        assert len(failed) == 0

        # Metrics that don't meet thresholds
        bad_metrics = {
            'accuracy': 0.60,
            'precision': 0.65,
            'recall': 0.65,
            'f1_score': 0.65
        }

        meets, failed = evaluator.check_model_thresholds(bad_metrics)
        assert not meets
        assert len(failed) > 0

    def test_compare_models(self, sample_model):
        """Test model comparison."""
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.datasets import make_classification

        X, y = make_classification(n_samples=100, n_features=10, random_state=42)

        # Train multiple models
        rf = RandomForestClassifier(n_estimators=10, random_state=42)
        rf.fit(X, y)

        lr = LogisticRegression(random_state=42)
        lr.fit(X, y)

        models = {
            'random_forest': rf,
            'logistic_regression': lr
        }

        evaluator = ModelEvaluator()
        comparison = evaluator.compare_models(models, X, y)

        assert len(comparison) == 2
        assert 'model' in comparison.columns
        assert 'f1_score' in comparison.columns
