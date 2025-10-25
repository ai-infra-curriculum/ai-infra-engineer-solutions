"""Model deployment orchestration."""

import mlflow
from typing import Dict, Any, Optional
import time

from ..common.config import config
from ..common.logger import get_logger
from ..training.registry import ModelRegistry
from .kubernetes_client import KubernetesClient

logger = get_logger(__name__)


class ModelDeployer:
    """Orchestrates model deployment to Kubernetes."""

    def __init__(self):
        """Initialize model deployer."""
        self.registry = ModelRegistry()
        self.k8s_client = KubernetesClient()
        self.deployment_name = config.MODEL_DEPLOYMENT_NAME

    def deploy_model(
        self,
        model_name: Optional[str] = None,
        version: Optional[str] = None,
        stage: str = 'Production',
        replicas: Optional[int] = None
    ) -> bool:
        """
        Deploy a model to Kubernetes.

        Args:
            model_name: Name of the model to deploy
            version: Model version (if None, uses stage)
            stage: Model stage to deploy from
            replicas: Number of replicas (optional)

        Returns:
            True if deployment successful, False otherwise
        """
        if model_name is None:
            model_name = config.MODEL_NAME

        logger.info(f"Deploying model {model_name}")

        try:
            # Get model information
            if version:
                model_info = self.registry.get_model_version(model_name, version)
            else:
                model_info = self.registry.get_latest_model_version(model_name, stage)

            if not model_info:
                logger.error(f"Model {model_name} not found")
                return False

            version = model_info['version']
            run_id = model_info['run_id']

            logger.info(f"Deploying model version {version} from run {run_id}")

            # Build image tag
            image_tag = f"model-server:{version}"

            # Update deployment
            success = self.k8s_client.update_deployment_image(
                name=self.deployment_name,
                image=image_tag
            )

            if not success:
                logger.error("Failed to update deployment")
                return False

            # Scale deployment if specified
            if replicas is not None:
                self.k8s_client.scale_deployment(self.deployment_name, replicas)

            # Wait for rollout
            rollout_success = self.k8s_client.wait_for_deployment_rollout(
                name=self.deployment_name,
                timeout=300
            )

            if not rollout_success:
                logger.error("Deployment rollout failed")
                # Attempt rollback
                self.rollback_deployment()
                return False

            # Run smoke tests
            smoke_test_passed = self.run_smoke_tests()

            if not smoke_test_passed:
                logger.error("Smoke tests failed")
                # Attempt rollback
                self.rollback_deployment()
                return False

            logger.info(f"Successfully deployed model {model_name} version {version}")
            return True

        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            return False

    def rollback_deployment(self) -> bool:
        """
        Rollback deployment to previous version.

        Returns:
            True if rollback successful, False otherwise
        """
        logger.info("Attempting deployment rollback")

        success = self.k8s_client.rollback_deployment(self.deployment_name)

        if success:
            # Wait for rollback to complete
            self.k8s_client.wait_for_deployment_rollout(
                name=self.deployment_name,
                timeout=300
            )
            logger.info("Rollback completed")
        else:
            logger.error("Rollback failed")

        return success

    def run_smoke_tests(self) -> bool:
        """
        Run smoke tests on deployed model.

        Returns:
            True if tests pass, False otherwise
        """
        logger.info("Running smoke tests")

        try:
            # Get deployment status
            deployment = self.k8s_client.get_deployment(self.deployment_name)

            if not deployment:
                logger.error("Deployment not found")
                return False

            # Check if all replicas are available
            replicas = deployment['replicas']
            available = deployment.get('available_replicas', 0)

            if available < replicas:
                logger.error(f"Not all replicas available: {available}/{replicas}")
                return False

            # Additional health checks could be added here
            # For example: HTTP health check, model inference test, etc.

            logger.info("Smoke tests passed")
            return True

        except Exception as e:
            logger.error(f"Smoke tests failed: {e}")
            return False

    def get_deployment_status(self) -> Dict[str, Any]:
        """
        Get current deployment status.

        Returns:
            Deployment status information
        """
        deployment = self.k8s_client.get_deployment(self.deployment_name)

        if not deployment:
            return {'status': 'not_found'}

        return {
            'status': 'running',
            'name': deployment['name'],
            'replicas': deployment['replicas'],
            'available_replicas': deployment['available_replicas'],
            'ready_replicas': deployment['ready_replicas'],
            'image': deployment['image']
        }

    def promote_and_deploy(
        self,
        model_name: Optional[str] = None,
        version: str = None
    ) -> bool:
        """
        Promote model to production and deploy.

        Args:
            model_name: Name of the model
            version: Model version to promote

        Returns:
            True if successful, False otherwise
        """
        if model_name is None:
            model_name = config.MODEL_NAME

        logger.info(f"Promoting and deploying {model_name} version {version}")

        # Set minimum metrics for production
        min_metrics = {
            'test_accuracy': config.MIN_ACCURACY,
            'test_precision': config.MIN_PRECISION,
            'test_recall': config.MIN_RECALL,
            'test_f1': config.MIN_F1_SCORE
        }

        # Promote to production
        promoted = self.registry.promote_to_production(
            model_name,
            version,
            min_metrics=min_metrics
        )

        if not promoted:
            logger.error("Model promotion failed")
            return False

        # Deploy to Kubernetes
        deployed = self.deploy_model(
            model_name=model_name,
            version=version,
            stage='Production'
        )

        return deployed

    def canary_deployment(
        self,
        model_name: Optional[str] = None,
        version: str = None,
        canary_percentage: int = 10
    ) -> bool:
        """
        Perform canary deployment.

        Args:
            model_name: Name of the model
            version: Model version
            canary_percentage: Percentage of traffic for canary

        Returns:
            True if successful, False otherwise
        """
        if model_name is None:
            model_name = config.MODEL_NAME

        logger.info(
            f"Starting canary deployment for {model_name} version {version} "
            f"({canary_percentage}% traffic)"
        )

        # This is a simplified canary deployment
        # In production, you would use service mesh (Istio, Linkerd) or ingress rules

        # For now, we'll deploy to staging first
        success = self.deploy_model(
            model_name=model_name,
            version=version,
            stage='Staging'
        )

        if success:
            logger.info(
                f"Canary deployment successful. Monitor metrics before full rollout."
            )

        return success
