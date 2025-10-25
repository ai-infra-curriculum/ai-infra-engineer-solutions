"""Data ingestion, validation, and preprocessing pipeline."""

from datetime import datetime, timedelta
from airflow.decorators import dag, task
import pandas as pd
import time

# Add src to path
import sys
sys.path.insert(0, '/opt/airflow')

from src.data.ingestion import DataIngestor
from src.data.validation import DataValidator
from src.data.preprocessing import DataPreprocessor
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
    dag_id='data_pipeline',
    default_args=default_args,
    description='Data ingestion, validation, and preprocessing pipeline',
    schedule_interval='@daily',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['data', 'mlops'],
)
def data_pipeline():
    """Data pipeline DAG."""

    @task()
    def ingest_data() -> str:
        """
        Ingest data from source.

        Returns:
            Path to ingested data file
        """
        logger.info("Starting data ingestion")
        start_time = time.time()

        try:
            ingestor = DataIngestor()

            # Generate synthetic data for this example
            # In production, you would fetch from actual data source
            df = ingestor.generate_synthetic_data(n_samples=10000)

            # Save data
            filename = f"churn_data_{datetime.now().strftime('%Y%m%d')}.csv"
            file_path = ingestor.save_data(df, filename, upload_to_s3=True)

            # Record metrics
            metrics = MetricsCollector()
            metrics.record_data_processing(
                stage='ingestion',
                num_rows=len(df)
            )

            duration = time.time() - start_time
            metrics.record_pipeline_run(
                pipeline_name='data_ingestion',
                status='success',
                duration=duration
            )

            logger.info(f"Data ingestion completed in {duration:.2f}s")
            return file_path

        except Exception as e:
            logger.error(f"Data ingestion failed: {e}")
            metrics = MetricsCollector()
            metrics.record_pipeline_run(
                pipeline_name='data_ingestion',
                status='failed',
                duration=time.time() - start_time
            )
            raise

    @task()
    def validate_data(file_path: str) -> dict:
        """
        Validate data quality.

        Args:
            file_path: Path to data file

        Returns:
            Validation report as dictionary
        """
        logger.info("Starting data validation")
        start_time = time.time()

        try:
            ingestor = DataIngestor()
            validator = DataValidator()

            # Load data
            df = pd.read_csv(file_path)

            # Validate
            report = validator.validate(df)

            # Record metrics
            metrics = MetricsCollector()
            metrics.record_data_processing(
                stage='validation',
                num_rows=len(df),
                quality_score=report.data_quality_score
            )

            duration = time.time() - start_time
            metrics.record_pipeline_run(
                pipeline_name='data_validation',
                status='success' if report.is_valid else 'failed',
                duration=duration
            )

            if not report.is_valid:
                logger.error(f"Data validation failed: {report.validation_errors}")
                raise ValueError("Data validation failed")

            logger.info(
                f"Data validation completed in {duration:.2f}s. "
                f"Quality score: {report.data_quality_score:.3f}"
            )

            return report.to_dict()

        except Exception as e:
            logger.error(f"Data validation failed: {e}")
            metrics = MetricsCollector()
            metrics.record_pipeline_run(
                pipeline_name='data_validation',
                status='failed',
                duration=time.time() - start_time
            )
            raise

    @task()
    def preprocess_data(file_path: str, validation_report: dict) -> dict:
        """
        Preprocess data and split into train/test.

        Args:
            file_path: Path to data file
            validation_report: Validation report

        Returns:
            Dictionary with paths to processed data files
        """
        logger.info("Starting data preprocessing")
        start_time = time.time()

        try:
            preprocessor = DataPreprocessor()

            # Load data
            df = pd.read_csv(file_path)

            # Preprocess
            X, y = preprocessor.preprocess(df, is_training=True)

            # Split data
            X_train, X_test, y_train, y_test = preprocessor.split_data(X, y)

            # Save processed data
            paths = preprocessor.save_processed_data(
                X_train, X_test, y_train, y_test
            )

            # Save preprocessor
            preprocessor_path = preprocessor.save_preprocessor()
            paths['preprocessor'] = preprocessor_path

            # Record metrics
            metrics = MetricsCollector()
            metrics.record_data_processing(
                stage='preprocessing',
                num_rows=len(X_train) + len(X_test)
            )

            duration = time.time() - start_time
            metrics.record_pipeline_run(
                pipeline_name='data_preprocessing',
                status='success',
                duration=duration
            )

            logger.info(
                f"Data preprocessing completed in {duration:.2f}s. "
                f"Train: {len(X_train)}, Test: {len(X_test)}"
            )

            return paths

        except Exception as e:
            logger.error(f"Data preprocessing failed: {e}")
            metrics = MetricsCollector()
            metrics.record_pipeline_run(
                pipeline_name='data_preprocessing',
                status='failed',
                duration=time.time() - start_time
            )
            raise

    @task()
    def commit_to_dvc(processed_paths: dict) -> str:
        """
        Commit processed data to DVC.

        Args:
            processed_paths: Dictionary with paths to processed files

        Returns:
            DVC commit hash
        """
        logger.info("Committing data to DVC")

        try:
            # In a real implementation, this would use DVC Python API
            # For now, we'll simulate it
            import subprocess
            import os

            # Add files to DVC
            for key, path in processed_paths.items():
                if key != 'preprocessor' and os.path.exists(path):
                    logger.info(f"Adding {path} to DVC")
                    # subprocess.run(['dvc', 'add', path], check=True)

            # Push to remote
            # subprocess.run(['dvc', 'push'], check=True)

            commit_hash = f"dvc_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            logger.info(f"Data committed to DVC: {commit_hash}")

            return commit_hash

        except Exception as e:
            logger.error(f"DVC commit failed: {e}")
            raise

    # Define task dependencies
    raw_data_path = ingest_data()
    validation_report = validate_data(raw_data_path)
    processed_paths = preprocess_data(raw_data_path, validation_report)
    dvc_commit = commit_to_dvc(processed_paths)


# Instantiate the DAG
data_pipeline_dag = data_pipeline()
