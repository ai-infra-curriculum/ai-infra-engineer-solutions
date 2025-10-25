"""Unit tests for data ingestion module."""

import pytest
import pandas as pd
from pathlib import Path

import sys
sys.path.insert(0, '/opt/airflow')

from src.data.ingestion import DataIngestor


class TestDataIngestor:
    """Test DataIngestor class."""

    def test_initialization(self, temp_dir, monkeypatch):
        """Test DataIngestor initialization."""
        monkeypatch.setenv('DATA_DIR', str(temp_dir))
        monkeypatch.setenv('RAW_DATA_PATH', str(temp_dir / 'raw'))

        ingestor = DataIngestor()

        assert ingestor.raw_data_path.exists()

    def test_generate_synthetic_data(self, temp_dir, monkeypatch):
        """Test synthetic data generation."""
        monkeypatch.setenv('DATA_DIR', str(temp_dir))
        monkeypatch.setenv('RAW_DATA_PATH', str(temp_dir / 'raw'))

        ingestor = DataIngestor()
        df = ingestor.generate_synthetic_data(n_samples=100)

        assert len(df) == 100
        assert 'Churn' in df.columns
        assert 'tenure' in df.columns
        assert 'monthly_charges' in df.columns

    def test_ingest_from_csv(self, temp_dir, sample_data, monkeypatch):
        """Test CSV ingestion."""
        monkeypatch.setenv('DATA_DIR', str(temp_dir))
        monkeypatch.setenv('RAW_DATA_PATH', str(temp_dir / 'raw'))

        # Save sample data
        csv_path = temp_dir / 'test_data.csv'
        sample_data.to_csv(csv_path, index=False)

        ingestor = DataIngestor()
        df = ingestor.ingest_from_csv(str(csv_path))

        assert len(df) == len(sample_data)
        assert list(df.columns) == list(sample_data.columns)

    def test_save_and_load_data(self, temp_dir, sample_data, monkeypatch):
        """Test saving and loading data."""
        monkeypatch.setenv('DATA_DIR', str(temp_dir))
        monkeypatch.setenv('RAW_DATA_PATH', str(temp_dir / 'raw'))
        monkeypatch.setenv('AWS_ENDPOINT_URL', 'http://localhost:9000')

        ingestor = DataIngestor()

        # Save data (without S3)
        saved_path = ingestor.save_data(sample_data, 'test.csv', upload_to_s3=False)

        assert Path(saved_path).exists()

        # Load data
        loaded_df = ingestor.load_data('test.csv', from_s3=False)

        assert len(loaded_df) == len(sample_data)
        assert list(loaded_df.columns) == list(sample_data.columns)
