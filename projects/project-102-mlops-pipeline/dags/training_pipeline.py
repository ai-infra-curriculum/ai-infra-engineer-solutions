"""Model training pipeline with MLflow tracking."""

from datetime import datetime, timedelta
from airflow.decorators import dag, task
from airflow.sensors.external_task import ExternalTaskSensor
import pandas as pd
import time

# Add src to path
import sys
sys.path.insert(0, '/opt/airflow')

from src.training.trainer import ModelTrainer
from src.training.evaluator import ModelEvaluator
from src.training.registry import ModelRegistry
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
    dag_id='training_pipeline',
    default_args=default_args,
    description='Model training pipeline with MLflow tracking',
    schedule_interval='@weekly',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['training', 'mlops'],
)
def training_pipeline():
    """Training pipeline DAG."""

    # Wait for data pipeline to complete
    wait_for_data = ExternalTaskSensor(
        task_id='wait_for_data_pipeline',
        external_dag_id='data_pipeline',
        external_task_id=None,  # Wait for entire DAG
        timeout=600,
        allowed_states=['success'],
        failed_states=['failed', 'skipped'],
        mode='reschedule',
    )

    @task()
    def load_data() -> dict:
        """
        Load processed data.

        Returns:
            Dictionary with data
        """
        logger.info("Loading processed data")

        try:
            from src.data.preprocessing import DataPreprocessor
            preprocessor = DataPreprocessor()

            # Load processed data
            X_train = pd.read_csv(preprocessor.processed_data_path / 'X_train.csv')
            X_test = pd.read_csv(preprocessor.processed_data_path / 'X_test.csv')
            y_train = pd.read_csv(preprocessor.processed_data_path / 'y_train.csv')['Churn']
            y_test = pd.read_csv(preprocessor.processed_data_path / 'y_test.csv')['Churn']

            logger.info(
                f"Loaded data - Train: {len(X_train)}, Test: {len(X_test)}"
            )

            return {
                'train_size': len(X_train),
                'test_size': len(X_test),
                'n_features': X_train.shape[1]
            }

        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            raise

    @task()
    def train_baseline_models(data_info: dict) -> dict:
        """
        Train baseline models.

        Args:
            data_info: Information about the data

        Returns:
            Dictionary with training results
        """
        logger.info("Training baseline models")
        start_time = time.time()

        try:
            from src.data.preprocessing import DataPreprocessor
            preprocessor = DataPreprocessor()

            # Load data
            X_train = pd.read_csv(preprocessor.processed_data_path / 'X_train.csv')
            X_test = pd.read_csv(preprocessor.processed_data_path / 'X_test.csv')
            y_train = pd.read_csv(preprocessor.processed_data_path / 'y_train.csv')['Churn']
            y_test = pd.read_csv(preprocessor.processed_data_path / 'y_test.csv')['Churn']

            # Train models
            trainer = ModelTrainer()
            results = trainer.train_all_models(X_train, y_train, X_test, y_test)

            # Collect results
            training_results = {}
            for model_name, (model, run_id) in results.items():
                evaluator = ModelEvaluator()
                metrics = evaluator.evaluate_model(model, X_test, y_test, model_name)

                training_results[model_name] = {
                    'run_id': run_id,
                    'metrics': metrics
                }

                # Record metrics
                metrics_collector = MetricsCollector()
                metrics_collector.record_model_training(
                    model_type=model_name,
                    duration=time.time() - start_time,
                    metrics=metrics,
                    model_name=config.MODEL_NAME,
                    model_version=run_id
                )

            duration = time.time() - start_time
            logger.info(
                f"Trained {len(results)} models in {duration:.2f}s"
            )

            return training_results

        except Exception as e:
            logger.error(f"Training failed: {e}")
            raise

    @task()
    def select_best_model(training_results: dict) -> dict:
        """
        Select best model based on metrics.

        Args:
            training_results: Training results for all models

        Returns:
            Best model information
        """
        logger.info("Selecting best model")

        try:
            # Find model with highest F1 score
            best_model_name = None
            best_f1_score = 0
            best_run_id = None

            for model_name, result in training_results.items():
                f1_score = result['metrics'].get('f1_score', 0)
                if f1_score > best_f1_score:
                    best_f1_score = f1_score
                    best_model_name = model_name
                    best_run_id = result['run_id']

            logger.info(
                f"Best model: {best_model_name} with F1={best_f1_score:.4f}"
            )

            return {
                'model_name': best_model_name,
                'run_id': best_run_id,
                'f1_score': best_f1_score,
                'metrics': training_results[best_model_name]['metrics']
            }

        except Exception as e:
            logger.error(f"Model selection failed: {e}")
            raise

    @task()
    def register_best_model(best_model_info: dict) -> dict:
        """
        Register best model to MLflow Model Registry.

        Args:
            best_model_info: Information about best model

        Returns:
            Model registry information
        """
        logger.info("Registering best model")

        try:
            registry = ModelRegistry()

            # Register model
            version = registry.register_model(
                run_id=best_model_info['run_id'],
                tags={
                    'model_type': best_model_info['model_name'],
                    'f1_score': str(best_model_info['f1_score'])
                }
            )

            # Transition to Staging
            registry.transition_model_stage(
                model_name=config.MODEL_NAME,
                version=version,
                stage='Staging'
            )

            logger.info(
                f"Registered model version {version} in Staging"
            )

            return {
                'model_name': config.MODEL_NAME,
                'version': version,
                'stage': 'Staging',
                'run_id': best_model_info['run_id']
            }

        except Exception as e:
            logger.error(f"Model registration failed: {e}")
            raise

    @task()
    def validate_model_performance(registry_info: dict) -> bool:
        """
        Validate model performance against thresholds.

        Args:
            registry_info: Model registry information

        Returns:
            True if validation passed
        """
        logger.info("Validating model performance")

        try:
            from src.data.preprocessing import DataPreprocessor
            preprocessor = DataPreprocessor()
            evaluator = ModelEvaluator()
            registry = ModelRegistry()

            # Load test data
            X_test = pd.read_csv(preprocessor.processed_data_path / 'X_test.csv')
            y_test = pd.read_csv(preprocessor.processed_data_path / 'y_test.csv')['Churn']

            # Load model from registry
            model = registry.load_model(
                model_name=registry_info['model_name'],
                version=registry_info['version']
            )

            # Evaluate
            metrics = evaluator.evaluate_model(model, X_test, y_test)

            # Check thresholds
            meets_thresholds, failed_metrics = evaluator.check_model_thresholds(metrics)

            if not meets_thresholds:
                logger.warning(
                    f"Model does not meet performance thresholds: {failed_metrics}"
                )
                return False

            logger.info("Model passed performance validation")
            return True

        except Exception as e:
            logger.error(f"Model validation failed: {e}")
            return False

    @task.branch()
    def decide_promotion(validation_passed: bool) -> str:
        """
        Decide whether to promote model to production.

        Args:
            validation_passed: Whether validation passed

        Returns:
            Task ID to execute next
        """
        if validation_passed:
            logger.info("Model approved for production")
            return 'trigger_deployment'
        else:
            logger.warning("Model not approved for production")
            return 'skip_deployment'

    @task()
    def trigger_deployment():
        """Trigger deployment pipeline."""
        logger.info("Triggering deployment pipeline")
        # In a real implementation, this would trigger the deployment DAG
        return "deployment_triggered"

    @task()
    def skip_deployment():
        """Skip deployment."""
        logger.info("Skipping deployment")
        return "deployment_skipped"

    # Define task dependencies
    data_ready = wait_for_data
    data_info = load_data()
    training_results = train_baseline_models(data_info)
    best_model = select_best_model(training_results)
    registry_info = register_best_model(best_model)
    validation_passed = validate_model_performance(registry_info)
    promotion_decision = decide_promotion(validation_passed)

    promotion_decision >> [trigger_deployment(), skip_deployment()]

    # Ensure data is ready before loading
    data_ready >> data_info


# Instantiate the DAG
training_pipeline_dag = training_pipeline()
