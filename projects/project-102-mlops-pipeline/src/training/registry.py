"""Model registry management with MLflow."""

import mlflow
from mlflow.tracking import MlflowClient
from typing import Optional, List, Dict, Any
import time

from ..common.config import config
from ..common.logger import get_logger

logger = get_logger(__name__)


class ModelRegistry:
    """Manages model lifecycle in MLflow Model Registry."""

    def __init__(self):
        """Initialize model registry."""
        mlflow.set_tracking_uri(config.MLFLOW_TRACKING_URI)
        self.client = MlflowClient()
        self.model_name = config.MODEL_NAME

    def register_model(
        self,
        run_id: str,
        model_name: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Register a model from a run.

        Args:
            run_id: MLflow run ID
            model_name: Name for the registered model
            tags: Optional tags for the model version

        Returns:
            Model version
        """
        if model_name is None:
            model_name = self.model_name

        logger.info(f"Registering model from run {run_id}")

        model_uri = f"runs:/{run_id}/model"

        # Register model
        result = mlflow.register_model(model_uri, model_name)

        version = result.version

        logger.info(f"Registered model {model_name} version {version}")

        # Add tags if provided
        if tags:
            for key, value in tags.items():
                self.client.set_model_version_tag(model_name, version, key, value)

        return version

    def transition_model_stage(
        self,
        model_name: Optional[str],
        version: str,
        stage: str,
        archive_existing: bool = True
    ) -> Dict[str, Any]:
        """
        Transition model to a different stage.

        Args:
            model_name: Name of the registered model
            version: Model version
            stage: Target stage (Staging, Production, Archived)
            archive_existing: Whether to archive existing models in target stage

        Returns:
            Model version details
        """
        if model_name is None:
            model_name = self.model_name

        logger.info(f"Transitioning {model_name} v{version} to {stage}")

        # Archive existing models in the target stage if requested
        if archive_existing and stage in ['Staging', 'Production']:
            self._archive_existing_models(model_name, stage)

        # Transition to new stage
        self.client.transition_model_version_stage(
            name=model_name,
            version=version,
            stage=stage
        )

        logger.info(f"Successfully transitioned to {stage}")

        return self.get_model_version(model_name, version)

    def _archive_existing_models(self, model_name: str, stage: str):
        """Archive existing models in a stage."""
        versions = self.client.get_latest_versions(model_name, stages=[stage])

        for version in versions:
            logger.info(f"Archiving {model_name} v{version.version} from {stage}")
            self.client.transition_model_version_stage(
                name=model_name,
                version=version.version,
                stage='Archived'
            )

    def get_model_version(
        self,
        model_name: Optional[str],
        version: str
    ) -> Dict[str, Any]:
        """
        Get model version details.

        Args:
            model_name: Name of the registered model
            version: Model version

        Returns:
            Model version details
        """
        if model_name is None:
            model_name = self.model_name

        mv = self.client.get_model_version(model_name, version)

        return {
            'name': mv.name,
            'version': mv.version,
            'stage': mv.current_stage,
            'run_id': mv.run_id,
            'status': mv.status,
            'creation_timestamp': mv.creation_timestamp,
            'last_updated_timestamp': mv.last_updated_timestamp,
            'description': mv.description,
            'tags': mv.tags
        }

    def get_latest_model_version(
        self,
        model_name: Optional[str],
        stage: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get latest model version.

        Args:
            model_name: Name of the registered model
            stage: Filter by stage (None for any stage)

        Returns:
            Latest model version details or None
        """
        if model_name is None:
            model_name = self.model_name

        stages = [stage] if stage else ['None', 'Staging', 'Production']

        try:
            versions = self.client.get_latest_versions(model_name, stages=stages)
            if not versions:
                return None

            # Get the most recent one
            latest = max(versions, key=lambda x: x.creation_timestamp)

            return {
                'name': latest.name,
                'version': latest.version,
                'stage': latest.current_stage,
                'run_id': latest.run_id,
                'status': latest.status,
                'creation_timestamp': latest.creation_timestamp,
                'last_updated_timestamp': latest.last_updated_timestamp
            }
        except Exception as e:
            logger.error(f"Failed to get latest model version: {e}")
            return None

    def load_model(
        self,
        model_name: Optional[str] = None,
        version: Optional[str] = None,
        stage: Optional[str] = 'Production'
    ) -> Any:
        """
        Load a model from the registry.

        Args:
            model_name: Name of the registered model
            version: Model version (if None, loads from stage)
            stage: Stage to load from (if version is None)

        Returns:
            Loaded model
        """
        if model_name is None:
            model_name = self.model_name

        if version:
            model_uri = f"models:/{model_name}/{version}"
        else:
            model_uri = f"models:/{model_name}/{stage}"

        logger.info(f"Loading model from {model_uri}")

        model = mlflow.sklearn.load_model(model_uri)

        logger.info("Model loaded successfully")
        return model

    def compare_models(
        self,
        model_name: Optional[str],
        version1: str,
        version2: str
    ) -> Dict[str, Any]:
        """
        Compare metrics between two model versions.

        Args:
            model_name: Name of the registered model
            version1: First model version
            version2: Second model version

        Returns:
            Comparison results
        """
        if model_name is None:
            model_name = self.model_name

        logger.info(f"Comparing {model_name} v{version1} vs v{version2}")

        # Get model versions
        mv1 = self.client.get_model_version(model_name, version1)
        mv2 = self.client.get_model_version(model_name, version2)

        # Get runs
        run1 = self.client.get_run(mv1.run_id)
        run2 = self.client.get_run(mv2.run_id)

        # Compare metrics
        metrics_comparison = {}
        all_metrics = set(run1.data.metrics.keys()) | set(run2.data.metrics.keys())

        for metric in all_metrics:
            val1 = run1.data.metrics.get(metric, None)
            val2 = run2.data.metrics.get(metric, None)

            if val1 is not None and val2 is not None:
                diff = val2 - val1
                pct_change = (diff / val1) * 100 if val1 != 0 else 0

                metrics_comparison[metric] = {
                    'version1': val1,
                    'version2': val2,
                    'difference': diff,
                    'percent_change': pct_change
                }

        return {
            'model_name': model_name,
            'version1': version1,
            'version2': version2,
            'metrics_comparison': metrics_comparison
        }

    def get_production_model_info(
        self,
        model_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get information about the current production model.

        Args:
            model_name: Name of the registered model

        Returns:
            Production model info or None
        """
        if model_name is None:
            model_name = self.model_name

        return self.get_latest_model_version(model_name, stage='Production')

    def promote_to_production(
        self,
        model_name: Optional[str],
        version: str,
        min_metrics: Optional[Dict[str, float]] = None
    ) -> bool:
        """
        Promote a model to production after validation.

        Args:
            model_name: Name of the registered model
            version: Model version to promote
            min_metrics: Minimum required metrics for promotion

        Returns:
            True if promotion successful, False otherwise
        """
        if model_name is None:
            model_name = self.model_name

        logger.info(f"Attempting to promote {model_name} v{version} to Production")

        # Get model version
        mv = self.client.get_model_version(model_name, version)
        run = self.client.get_run(mv.run_id)

        # Validate metrics if required
        if min_metrics:
            for metric, min_value in min_metrics.items():
                actual_value = run.data.metrics.get(metric)
                if actual_value is None or actual_value < min_value:
                    logger.error(
                        f"Model failed metric validation: {metric} = {actual_value} < {min_value}"
                    )
                    return False

        # Promote to production
        self.transition_model_stage(model_name, version, 'Production', archive_existing=True)

        logger.info(f"Successfully promoted {model_name} v{version} to Production")
        return True

    def list_model_versions(
        self,
        model_name: Optional[str] = None,
        stage: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List all versions of a model.

        Args:
            model_name: Name of the registered model
            stage: Filter by stage (optional)

        Returns:
            List of model version details
        """
        if model_name is None:
            model_name = self.model_name

        try:
            if stage:
                versions = self.client.get_latest_versions(model_name, stages=[stage])
            else:
                versions = self.client.search_model_versions(f"name='{model_name}'")

            return [{
                'name': v.name,
                'version': v.version,
                'stage': v.current_stage,
                'run_id': v.run_id,
                'status': v.status,
                'creation_timestamp': v.creation_timestamp
            } for v in versions]

        except Exception as e:
            logger.error(f"Failed to list model versions: {e}")
            return []
