"""Model deployment pipeline."""

from datetime import datetime, timedelta
from airflow.decorators import dag, task
from airflow.sensors.external_task import ExternalTaskSensor
import time

# Add src to path
import sys
sys.path.insert(0, '/opt/airflow')

from src.deployment.deployer import ModelDeployer
from src.training.registry import ModelRegistry
from src.monitoring.drift_detector import DriftDetector
from src.common.config import config
from src.common.logger import get_logger
from src.monitoring.metrics_collector import MetricsCollector

logger = get_logger(__name__)

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}


@dag(
    dag_id='deployment_pipeline',
    default_args=default_args,
    description='Automated model deployment pipeline',
    schedule_interval=None,  # Triggered manually or by training pipeline
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['deployment', 'mlops'],
)
def deployment_pipeline():
    """Deployment pipeline DAG."""

    @task()
    def get_staging_model() -> dict:
        """
        Get model from Staging stage.

        Returns:
            Model information
        """
        logger.info("Getting model from Staging")

        try:
            registry = ModelRegistry()
            model_info = registry.get_latest_model_version(
                model_name=config.MODEL_NAME,
                stage='Staging'
            )

            if not model_info:
                raise ValueError("No model found in Staging")

            logger.info(f"Found model version {model_info['version']} in Staging")
            return model_info

        except Exception as e:
            logger.error(f"Failed to get staging model: {e}")
            raise

    @task()
    def run_integration_tests(model_info: dict) -> bool:
        """
        Run integration tests on the model.

        Args:
            model_info: Model information

        Returns:
            True if tests pass
        """
        logger.info("Running integration tests")

        try:
            import pandas as pd
            from src.data.preprocessing import DataPreprocessor
            from src.training.registry import ModelRegistry

            registry = ModelRegistry()
            preprocessor = DataPreprocessor()

            # Load model
            model = registry.load_model(
                model_name=model_info['name'],
                version=model_info['version']
            )

            # Load test data
            X_test = pd.read_csv(preprocessor.processed_data_path / 'X_test.csv')

            # Run predictions
            predictions = model.predict(X_test[:100])  # Test on subset

            # Basic sanity checks
            assert len(predictions) == 100, "Prediction count mismatch"
            assert all(pred in [0, 1] for pred in predictions), "Invalid predictions"

            logger.info("Integration tests passed")
            return True

        except Exception as e:
            logger.error(f"Integration tests failed: {e}")
            return False

    @task()
    def deploy_to_production(model_info: dict, tests_passed: bool) -> dict:
        """
        Deploy model to production.

        Args:
            model_info: Model information
            tests_passed: Whether tests passed

        Returns:
            Deployment information
        """
        if not tests_passed:
            raise ValueError("Cannot deploy: integration tests failed")

        logger.info("Deploying model to production")
        start_time = time.time()

        try:
            deployer = ModelDeployer()
            metrics = MetricsCollector()

            # Promote to Production
            success = deployer.promote_and_deploy(
                model_name=model_info['name'],
                version=model_info['version']
            )

            if not success:
                raise RuntimeError("Deployment failed")

            duration = time.time() - start_time

            # Record metrics
            metrics.record_model_deployment(
                model_name=model_info['name'],
                status='success'
            )

            logger.info(f"Deployment completed in {duration:.2f}s")

            return {
                'model_name': model_info['name'],
                'version': model_info['version'],
                'deployment_time': duration,
                'status': 'success'
            }

        except Exception as e:
            logger.error(f"Deployment failed: {e}")

            # Record failure
            metrics = MetricsCollector()
            metrics.record_model_deployment(
                model_name=model_info['name'],
                status='failed'
            )
            raise

    @task()
    def verify_deployment(deployment_info: dict) -> bool:
        """
        Verify deployment is healthy.

        Args:
            deployment_info: Deployment information

        Returns:
            True if healthy
        """
        logger.info("Verifying deployment")

        try:
            deployer = ModelDeployer()

            # Get deployment status
            status = deployer.get_deployment_status()

            if status['status'] != 'running':
                logger.error(f"Deployment not running: {status}")
                return False

            # Check replicas
            if status['available_replicas'] < status['replicas']:
                logger.error("Not all replicas are available")
                return False

            logger.info("Deployment verification passed")
            return True

        except Exception as e:
            logger.error(f"Deployment verification failed: {e}")
            return False

    @task()
    def setup_monitoring(deployment_info: dict, verification_passed: bool):
        """
        Setup monitoring for deployed model.

        Args:
            deployment_info: Deployment information
            verification_passed: Whether verification passed
        """
        if not verification_passed:
            logger.warning("Skipping monitoring setup due to failed verification")
            return

        logger.info("Setting up monitoring")

        try:
            import pandas as pd
            from src.data.preprocessing import DataPreprocessor

            # Initialize drift detector with reference data
            drift_detector = DriftDetector()
            preprocessor = DataPreprocessor()

            # Load reference data (test set)
            X_test = pd.read_csv(preprocessor.processed_data_path / 'X_test.csv')
            y_test = pd.read_csv(preprocessor.processed_data_path / 'y_test.csv')['Churn']

            drift_detector.set_reference_data(X_test, y_test.values)

            logger.info("Monitoring setup completed")

        except Exception as e:
            logger.error(f"Monitoring setup failed: {e}")

    @task()
    def send_notification(deployment_info: dict):
        """
        Send deployment notification.

        Args:
            deployment_info: Deployment information
        """
        logger.info("Sending deployment notification")

        message = f"""
        Model Deployment Successful
        ===========================
        Model: {deployment_info['model_name']}
        Version: {deployment_info['version']}
        Status: {deployment_info['status']}
        Deployment Time: {deployment_info['deployment_time']:.2f}s

        The model is now serving traffic in production.
        """

        logger.info(message)
        # In production, this would send email/Slack notification

    # Define task dependencies
    model_info = get_staging_model()
    tests_passed = run_integration_tests(model_info)
    deployment_info = deploy_to_production(model_info, tests_passed)
    verification_passed = verify_deployment(deployment_info)
    setup_monitoring(deployment_info, verification_passed)
    send_notification(deployment_info)


# Instantiate the DAG
deployment_pipeline_dag = deployment_pipeline()
