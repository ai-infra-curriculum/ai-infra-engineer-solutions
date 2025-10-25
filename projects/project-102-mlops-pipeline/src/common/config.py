"""Configuration management for MLOps pipeline."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """Central configuration for all pipeline components."""

    # Environment
    ENVIRONMENT: str = os.getenv('ENVIRONMENT', 'development')

    # Data paths
    DATA_DIR: str = os.getenv('DATA_DIR', '/opt/airflow/data')
    RAW_DATA_PATH: str = os.getenv('RAW_DATA_PATH', f'{DATA_DIR}/raw')
    PROCESSED_DATA_PATH: str = os.getenv('PROCESSED_DATA_PATH', f'{DATA_DIR}/processed')
    MODELS_DIR: str = os.getenv('MODELS_DIR', '/opt/airflow/models')

    # MLflow configuration
    MLFLOW_TRACKING_URI: str = os.getenv('MLFLOW_TRACKING_URI', 'http://mlflow:5000')
    MLFLOW_EXPERIMENT_NAME: str = os.getenv('MLFLOW_EXPERIMENT_NAME', 'churn-prediction')
    MLFLOW_ARTIFACT_ROOT: str = os.getenv('MLFLOW_ARTIFACT_ROOT', 's3://mlflow-artifacts')

    # DVC configuration
    DVC_REMOTE_URL: str = os.getenv('DVC_REMOTE_URL', 's3://dvc-storage')

    # MinIO/S3 configuration
    AWS_ACCESS_KEY_ID: str = os.getenv('AWS_ACCESS_KEY_ID', 'minioadmin')
    AWS_SECRET_ACCESS_KEY: str = os.getenv('AWS_SECRET_ACCESS_KEY', 'minioadmin')
    AWS_ENDPOINT_URL: str = os.getenv('AWS_ENDPOINT_URL', 'http://minio:9000')
    S3_BUCKET: str = os.getenv('S3_BUCKET', 'mlops-data')

    # Database configuration
    POSTGRES_HOST: str = os.getenv('POSTGRES_HOST', 'postgres')
    POSTGRES_PORT: int = int(os.getenv('POSTGRES_PORT', '5432'))
    POSTGRES_DB: str = os.getenv('POSTGRES_DB', 'mlflow')
    POSTGRES_USER: str = os.getenv('POSTGRES_USER', 'mlflow')
    POSTGRES_PASSWORD: str = os.getenv('POSTGRES_PASSWORD', 'mlflow')

    # Model configuration
    MODEL_NAME: str = os.getenv('MODEL_NAME', 'churn-classifier')
    TARGET_COLUMN: str = os.getenv('TARGET_COLUMN', 'Churn')

    # Training configuration
    TRAIN_TEST_SPLIT: float = float(os.getenv('TRAIN_TEST_SPLIT', '0.2'))
    RANDOM_STATE: int = int(os.getenv('RANDOM_STATE', '42'))
    CV_FOLDS: int = int(os.getenv('CV_FOLDS', '5'))

    # Model thresholds
    MIN_ACCURACY: float = float(os.getenv('MIN_ACCURACY', '0.75'))
    MIN_PRECISION: float = float(os.getenv('MIN_PRECISION', '0.70'))
    MIN_RECALL: float = float(os.getenv('MIN_RECALL', '0.70'))
    MIN_F1_SCORE: float = float(os.getenv('MIN_F1_SCORE', '0.70'))

    # Monitoring configuration
    PROMETHEUS_PORT: int = int(os.getenv('PROMETHEUS_PORT', '9090'))
    GRAFANA_PORT: int = int(os.getenv('GRAFANA_PORT', '3000'))

    # Kubernetes configuration
    K8S_NAMESPACE: str = os.getenv('K8S_NAMESPACE', 'ml-serving')
    MODEL_DEPLOYMENT_NAME: str = os.getenv('MODEL_DEPLOYMENT_NAME', 'churn-model')

    # Alerting thresholds
    DRIFT_THRESHOLD: float = float(os.getenv('DRIFT_THRESHOLD', '0.1'))
    PERFORMANCE_DROP_THRESHOLD: float = float(os.getenv('PERFORMANCE_DROP_THRESHOLD', '0.05'))

    @property
    def postgres_connection_string(self) -> str:
        """Get PostgreSQL connection string."""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    def validate(self) -> bool:
        """Validate configuration."""
        required_fields = [
            'MLFLOW_TRACKING_URI',
            'MLFLOW_EXPERIMENT_NAME',
            'DATA_DIR',
            'MODEL_NAME',
        ]

        for field in required_fields:
            if not getattr(self, field):
                raise ValueError(f"Required configuration field '{field}' is not set")

        return True


# Global configuration instance
config = Config()
