"""Data ingestion module for fetching and loading data."""

import os
import pandas as pd
import requests
from typing import Optional
from pathlib import Path

from ..common.config import config
from ..common.logger import get_logger
from ..common.storage import StorageClient

logger = get_logger(__name__)


class DataIngestor:
    """Handles data ingestion from various sources."""

    def __init__(self):
        """Initialize data ingestor."""
        self.storage = StorageClient()
        self.raw_data_path = Path(config.RAW_DATA_PATH)
        self.raw_data_path.mkdir(parents=True, exist_ok=True)

    def ingest_from_url(self, url: str, filename: str) -> str:
        """
        Ingest data from a URL.

        Args:
            url: URL to fetch data from
            filename: Name to save the file as

        Returns:
            Path to the saved file
        """
        logger.info(f"Ingesting data from URL: {url}")

        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()

            file_path = self.raw_data_path / filename
            with open(file_path, 'wb') as f:
                f.write(response.content)

            logger.info(f"Data saved to {file_path}")

            # Upload to S3
            s3_key = f"raw/{filename}"
            self.storage.upload_file(str(file_path), s3_key)

            return str(file_path)

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch data from URL: {e}")
            raise

    def ingest_from_csv(self, csv_path: str) -> pd.DataFrame:
        """
        Ingest data from a local CSV file.

        Args:
            csv_path: Path to CSV file

        Returns:
            DataFrame with loaded data
        """
        logger.info(f"Ingesting data from CSV: {csv_path}")

        try:
            df = pd.read_csv(csv_path)
            logger.info(f"Loaded {len(df)} rows and {len(df.columns)} columns")
            return df

        except Exception as e:
            logger.error(f"Failed to load CSV: {e}")
            raise

    def generate_synthetic_data(self, n_samples: int = 10000) -> pd.DataFrame:
        """
        Generate synthetic churn data for testing.

        Args:
            n_samples: Number of samples to generate

        Returns:
            DataFrame with synthetic data
        """
        logger.info(f"Generating {n_samples} synthetic samples")

        import numpy as np
        from sklearn.datasets import make_classification

        # Generate features
        X, y = make_classification(
            n_samples=n_samples,
            n_features=15,
            n_informative=10,
            n_redundant=3,
            n_classes=2,
            weights=[0.7, 0.3],  # Imbalanced classes
            random_state=config.RANDOM_STATE
        )

        # Create DataFrame with meaningful column names
        feature_names = [
            'tenure',
            'monthly_charges',
            'total_charges',
            'contract_type',
            'payment_method',
            'internet_service',
            'online_security',
            'tech_support',
            'streaming_tv',
            'streaming_movies',
            'paperless_billing',
            'senior_citizen',
            'partner',
            'dependents',
            'multiple_lines'
        ]

        df = pd.DataFrame(X, columns=feature_names)
        df['Churn'] = y

        # Add some realistic transformations
        df['tenure'] = (df['tenure'] * 10 + 30).clip(0, 72).astype(int)
        df['monthly_charges'] = (df['monthly_charges'] * 20 + 70).clip(20, 120)
        df['total_charges'] = df['tenure'] * df['monthly_charges'] + np.random.normal(0, 100, n_samples)

        # Convert some features to categorical
        df['contract_type'] = pd.cut(df['contract_type'], bins=3, labels=['Month-to-month', 'One year', 'Two year'])
        df['payment_method'] = pd.cut(df['payment_method'], bins=4, labels=['Electronic check', 'Mailed check', 'Bank transfer', 'Credit card'])
        df['internet_service'] = pd.cut(df['internet_service'], bins=3, labels=['DSL', 'Fiber optic', 'No'])

        logger.info(f"Generated synthetic data with shape {df.shape}")
        return df

    def save_data(self, df: pd.DataFrame, filename: str, upload_to_s3: bool = True) -> str:
        """
        Save DataFrame to local storage and optionally S3.

        Args:
            df: DataFrame to save
            filename: Name of the file
            upload_to_s3: Whether to upload to S3

        Returns:
            Path to saved file
        """
        file_path = self.raw_data_path / filename
        df.to_csv(file_path, index=False)
        logger.info(f"Saved data to {file_path}")

        if upload_to_s3:
            s3_key = f"raw/{filename}"
            self.storage.upload_file(str(file_path), s3_key)

        return str(file_path)

    def load_data(self, filename: str, from_s3: bool = False) -> pd.DataFrame:
        """
        Load data from local storage or S3.

        Args:
            filename: Name of the file
            from_s3: Whether to load from S3

        Returns:
            DataFrame with loaded data
        """
        if from_s3:
            s3_key = f"raw/{filename}"
            local_path = self.raw_data_path / filename
            self.storage.download_file(s3_key, str(local_path))
            file_path = local_path
        else:
            file_path = self.raw_data_path / filename

        return self.ingest_from_csv(str(file_path))
