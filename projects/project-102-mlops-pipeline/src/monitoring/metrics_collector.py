"""Metrics collection for monitoring."""

import time
from typing import Dict, Any, Optional
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, push_to_gateway
import json

from ..common.config import config
from ..common.logger import get_logger

logger = get_logger(__name__)


class MetricsCollector:
    """Collects and exports metrics for monitoring."""

    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """
        Initialize metrics collector.

        Args:
            registry: Prometheus registry (optional)
        """
        self.registry = registry or CollectorRegistry()

        # Pipeline metrics
        self.pipeline_runs = Counter(
            'pipeline_runs_total',
            'Total number of pipeline runs',
            ['pipeline_name', 'status'],
            registry=self.registry
        )

        self.pipeline_duration = Histogram(
            'pipeline_duration_seconds',
            'Pipeline execution duration',
            ['pipeline_name'],
            registry=self.registry
        )

        # Data metrics
        self.data_rows_processed = Counter(
            'data_rows_processed_total',
            'Total number of data rows processed',
            ['stage'],
            registry=self.registry
        )

        self.data_quality_score = Gauge(
            'data_quality_score',
            'Data quality score (0-1)',
            registry=self.registry
        )

        # Model metrics
        self.model_training_duration = Histogram(
            'model_training_duration_seconds',
            'Model training duration',
            ['model_type'],
            registry=self.registry
        )

        self.model_accuracy = Gauge(
            'model_accuracy',
            'Model accuracy',
            ['model_name', 'model_version'],
            registry=self.registry
        )

        self.model_precision = Gauge(
            'model_precision',
            'Model precision',
            ['model_name', 'model_version'],
            registry=self.registry
        )

        self.model_recall = Gauge(
            'model_recall',
            'Model recall',
            ['model_name', 'model_version'],
            registry=self.registry
        )

        self.model_f1_score = Gauge(
            'model_f1_score',
            'Model F1 score',
            ['model_name', 'model_version'],
            registry=self.registry
        )

        # Deployment metrics
        self.model_deployments = Counter(
            'model_deployments_total',
            'Total number of model deployments',
            ['model_name', 'status'],
            registry=self.registry
        )

        # Drift metrics
        self.feature_drift_score = Gauge(
            'feature_drift_score',
            'Feature drift score',
            ['feature_name'],
            registry=self.registry
        )

        self.prediction_drift_score = Gauge(
            'prediction_drift_score',
            'Prediction drift score',
            registry=self.registry
        )

        # Inference metrics
        self.predictions_total = Counter(
            'predictions_total',
            'Total number of predictions',
            ['model_name', 'model_version'],
            registry=self.registry
        )

        self.prediction_latency = Histogram(
            'prediction_latency_seconds',
            'Prediction latency',
            ['model_name', 'model_version'],
            registry=self.registry
        )

    def record_pipeline_run(
        self,
        pipeline_name: str,
        status: str,
        duration: float
    ):
        """
        Record pipeline run metrics.

        Args:
            pipeline_name: Name of the pipeline
            status: Run status (success, failed)
            duration: Duration in seconds
        """
        self.pipeline_runs.labels(
            pipeline_name=pipeline_name,
            status=status
        ).inc()

        self.pipeline_duration.labels(
            pipeline_name=pipeline_name
        ).observe(duration)

        logger.info(
            f"Recorded pipeline run: {pipeline_name}, "
            f"status={status}, duration={duration:.2f}s"
        )

    def record_data_processing(
        self,
        stage: str,
        num_rows: int,
        quality_score: Optional[float] = None
    ):
        """
        Record data processing metrics.

        Args:
            stage: Processing stage
            num_rows: Number of rows processed
            quality_score: Data quality score (0-1)
        """
        self.data_rows_processed.labels(stage=stage).inc(num_rows)

        if quality_score is not None:
            self.data_quality_score.set(quality_score)

        logger.info(
            f"Recorded data processing: stage={stage}, "
            f"rows={num_rows}, quality={quality_score}"
        )

    def record_model_training(
        self,
        model_type: str,
        duration: float,
        metrics: Dict[str, float],
        model_name: str,
        model_version: str
    ):
        """
        Record model training metrics.

        Args:
            model_type: Type of model
            duration: Training duration in seconds
            metrics: Model performance metrics
            model_name: Model name
            model_version: Model version
        """
        self.model_training_duration.labels(
            model_type=model_type
        ).observe(duration)

        # Record performance metrics
        if 'accuracy' in metrics:
            self.model_accuracy.labels(
                model_name=model_name,
                model_version=model_version
            ).set(metrics['accuracy'])

        if 'precision' in metrics:
            self.model_precision.labels(
                model_name=model_name,
                model_version=model_version
            ).set(metrics['precision'])

        if 'recall' in metrics:
            self.model_recall.labels(
                model_name=model_name,
                model_version=model_version
            ).set(metrics['recall'])

        if 'f1_score' in metrics:
            self.model_f1_score.labels(
                model_name=model_name,
                model_version=model_version
            ).set(metrics['f1_score'])

        logger.info(
            f"Recorded model training: type={model_type}, "
            f"duration={duration:.2f}s, metrics={metrics}"
        )

    def record_model_deployment(
        self,
        model_name: str,
        status: str
    ):
        """
        Record model deployment metrics.

        Args:
            model_name: Model name
            status: Deployment status (success, failed)
        """
        self.model_deployments.labels(
            model_name=model_name,
            status=status
        ).inc()

        logger.info(f"Recorded model deployment: {model_name}, status={status}")

    def record_drift_detection(
        self,
        feature_drift_scores: Dict[str, float],
        prediction_drift_score: Optional[float] = None
    ):
        """
        Record drift detection metrics.

        Args:
            feature_drift_scores: Drift scores per feature
            prediction_drift_score: Overall prediction drift score
        """
        for feature_name, score in feature_drift_scores.items():
            self.feature_drift_score.labels(
                feature_name=feature_name
            ).set(score)

        if prediction_drift_score is not None:
            self.prediction_drift_score.set(prediction_drift_score)

        logger.info(f"Recorded drift metrics: {len(feature_drift_scores)} features")

    def record_prediction(
        self,
        model_name: str,
        model_version: str,
        latency: float
    ):
        """
        Record prediction metrics.

        Args:
            model_name: Model name
            model_version: Model version
            latency: Prediction latency in seconds
        """
        self.predictions_total.labels(
            model_name=model_name,
            model_version=model_version
        ).inc()

        self.prediction_latency.labels(
            model_name=model_name,
            model_version=model_version
        ).observe(latency)

    def export_metrics_to_file(self, filepath: str):
        """
        Export metrics to JSON file.

        Args:
            filepath: Path to export file
        """
        metrics = {
            'timestamp': time.time(),
            'metrics': {
                # Add metrics here
            }
        }

        with open(filepath, 'w') as f:
            json.dump(metrics, f, indent=2)

        logger.info(f"Exported metrics to {filepath}")

    def push_to_gateway(
        self,
        gateway: str,
        job: str
    ):
        """
        Push metrics to Prometheus Pushgateway.

        Args:
            gateway: Pushgateway address
            job: Job name
        """
        try:
            push_to_gateway(gateway, job=job, registry=self.registry)
            logger.info(f"Pushed metrics to {gateway}")
        except Exception as e:
            logger.error(f"Failed to push metrics: {e}")
