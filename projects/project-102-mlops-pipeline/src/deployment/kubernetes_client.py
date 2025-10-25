"""Kubernetes client for model deployment."""

from kubernetes import client, config as k8s_config
from kubernetes.client.rest import ApiException
from typing import Dict, Any, Optional
import time

from ..common.config import config
from ..common.logger import get_logger

logger = get_logger(__name__)


class KubernetesClient:
    """Client for Kubernetes operations."""

    def __init__(self):
        """Initialize Kubernetes client."""
        try:
            # Try to load in-cluster config first
            k8s_config.load_incluster_config()
            logger.info("Loaded in-cluster Kubernetes config")
        except k8s_config.ConfigException:
            # Fall back to kubeconfig
            try:
                k8s_config.load_kube_config()
                logger.info("Loaded Kubernetes config from kubeconfig")
            except k8s_config.ConfigException:
                logger.error("Could not load Kubernetes config")
                raise

        self.apps_v1 = client.AppsV1Api()
        self.core_v1 = client.CoreV1Api()
        self.namespace = config.K8S_NAMESPACE

    def get_deployment(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get deployment details.

        Args:
            name: Deployment name

        Returns:
            Deployment details or None
        """
        try:
            deployment = self.apps_v1.read_namespaced_deployment(
                name=name,
                namespace=self.namespace
            )
            return {
                'name': deployment.metadata.name,
                'replicas': deployment.spec.replicas,
                'available_replicas': deployment.status.available_replicas,
                'ready_replicas': deployment.status.ready_replicas,
                'image': deployment.spec.template.spec.containers[0].image
            }
        except ApiException as e:
            if e.status == 404:
                logger.warning(f"Deployment {name} not found")
                return None
            logger.error(f"Failed to get deployment: {e}")
            raise

    def update_deployment_image(
        self,
        name: str,
        image: str,
        container_name: Optional[str] = None
    ) -> bool:
        """
        Update deployment with new image.

        Args:
            name: Deployment name
            image: New container image
            container_name: Container name (defaults to first container)

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Updating deployment {name} with image {image}")

        try:
            # Get current deployment
            deployment = self.apps_v1.read_namespaced_deployment(
                name=name,
                namespace=self.namespace
            )

            # Update image
            if container_name is None:
                # Update first container
                deployment.spec.template.spec.containers[0].image = image
            else:
                # Find and update specific container
                for container in deployment.spec.template.spec.containers:
                    if container.name == container_name:
                        container.image = image
                        break

            # Apply update
            self.apps_v1.patch_namespaced_deployment(
                name=name,
                namespace=self.namespace,
                body=deployment
            )

            logger.info(f"Successfully updated deployment {name}")
            return True

        except ApiException as e:
            logger.error(f"Failed to update deployment: {e}")
            return False

    def wait_for_deployment_rollout(
        self,
        name: str,
        timeout: int = 300
    ) -> bool:
        """
        Wait for deployment rollout to complete.

        Args:
            name: Deployment name
            timeout: Timeout in seconds

        Returns:
            True if rollout successful, False otherwise
        """
        logger.info(f"Waiting for deployment {name} rollout...")

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                deployment = self.apps_v1.read_namespaced_deployment(
                    name=name,
                    namespace=self.namespace
                )

                replicas = deployment.spec.replicas or 0
                available = deployment.status.available_replicas or 0

                if available == replicas and available > 0:
                    logger.info(f"Deployment {name} rollout completed successfully")
                    return True

                logger.info(f"Waiting... ({available}/{replicas} replicas available)")
                time.sleep(10)

            except ApiException as e:
                logger.error(f"Error checking deployment status: {e}")
                return False

        logger.error(f"Deployment rollout timed out after {timeout}s")
        return False

    def scale_deployment(
        self,
        name: str,
        replicas: int
    ) -> bool:
        """
        Scale deployment to specified number of replicas.

        Args:
            name: Deployment name
            replicas: Number of replicas

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Scaling deployment {name} to {replicas} replicas")

        try:
            # Get current deployment
            deployment = self.apps_v1.read_namespaced_deployment(
                name=name,
                namespace=self.namespace
            )

            # Update replicas
            deployment.spec.replicas = replicas

            # Apply update
            self.apps_v1.patch_namespaced_deployment(
                name=name,
                namespace=self.namespace,
                body=deployment
            )

            logger.info(f"Successfully scaled deployment {name}")
            return True

        except ApiException as e:
            logger.error(f"Failed to scale deployment: {e}")
            return False

    def create_or_update_configmap(
        self,
        name: str,
        data: Dict[str, str]
    ) -> bool:
        """
        Create or update a ConfigMap.

        Args:
            name: ConfigMap name
            data: ConfigMap data

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Creating/updating ConfigMap {name}")

        configmap = client.V1ConfigMap(
            metadata=client.V1ObjectMeta(name=name),
            data=data
        )

        try:
            # Try to create
            self.core_v1.create_namespaced_config_map(
                namespace=self.namespace,
                body=configmap
            )
            logger.info(f"Created ConfigMap {name}")
            return True

        except ApiException as e:
            if e.status == 409:
                # ConfigMap exists, update it
                try:
                    self.core_v1.replace_namespaced_config_map(
                        name=name,
                        namespace=self.namespace,
                        body=configmap
                    )
                    logger.info(f"Updated ConfigMap {name}")
                    return True
                except ApiException as e2:
                    logger.error(f"Failed to update ConfigMap: {e2}")
                    return False
            else:
                logger.error(f"Failed to create ConfigMap: {e}")
                return False

    def get_pod_logs(
        self,
        label_selector: str,
        tail_lines: int = 100
    ) -> Dict[str, str]:
        """
        Get logs from pods matching label selector.

        Args:
            label_selector: Label selector (e.g., "app=model-server")
            tail_lines: Number of lines to retrieve

        Returns:
            Dictionary of {pod_name: logs}
        """
        try:
            pods = self.core_v1.list_namespaced_pod(
                namespace=self.namespace,
                label_selector=label_selector
            )

            logs = {}
            for pod in pods.items:
                pod_name = pod.metadata.name
                try:
                    log = self.core_v1.read_namespaced_pod_log(
                        name=pod_name,
                        namespace=self.namespace,
                        tail_lines=tail_lines
                    )
                    logs[pod_name] = log
                except ApiException as e:
                    logger.error(f"Failed to get logs for pod {pod_name}: {e}")

            return logs

        except ApiException as e:
            logger.error(f"Failed to list pods: {e}")
            return {}

    def rollback_deployment(
        self,
        name: str,
        revision: Optional[int] = None
    ) -> bool:
        """
        Rollback deployment to previous revision.

        Args:
            name: Deployment name
            revision: Revision number (None for previous)

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Rolling back deployment {name}")

        try:
            # Get deployment
            deployment = self.apps_v1.read_namespaced_deployment(
                name=name,
                namespace=self.namespace
            )

            # Trigger rollback by updating rollback annotation
            if deployment.metadata.annotations is None:
                deployment.metadata.annotations = {}

            deployment.metadata.annotations['kubernetes.io/change-cause'] = 'rollback'

            # Apply update
            self.apps_v1.patch_namespaced_deployment(
                name=name,
                namespace=self.namespace,
                body=deployment
            )

            logger.info(f"Initiated rollback for deployment {name}")
            return True

        except ApiException as e:
            logger.error(f"Failed to rollback deployment: {e}")
            return False
