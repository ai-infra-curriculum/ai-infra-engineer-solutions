"""Integration tests for end-to-end pipeline."""

import pytest
import pandas as pd
from pathlib import Path

import sys
sys.path.insert(0, '/opt/airflow')


class TestEndToEndPipeline:
    """Test end-to-end pipeline flow."""

    def test_data_pipeline_flow(self, temp_dir, monkeypatch):
        """Test complete data pipeline flow."""
        monkeypatch.setenv('DATA_DIR', str(temp_dir))
        monkeypatch.setenv('RAW_DATA_PATH', str(temp_dir / 'raw'))
        monkeypatch.setenv('PROCESSED_DATA_PATH', str(temp_dir / 'processed'))

        from src.data.ingestion import DataIngestor
        from src.data.validation import DataValidator
        from src.data.preprocessing import DataPreprocessor

        # Step 1: Ingest data
        ingestor = DataIngestor()
        df = ingestor.generate_synthetic_data(n_samples=500)
        file_path = ingestor.save_data(df, 'test.csv', upload_to_s3=False)

        assert Path(file_path).exists()

        # Step 2: Validate data
        validator = DataValidator()
        report = validator.validate(df)

        assert report.is_valid

        # Step 3: Preprocess data
        preprocessor = DataPreprocessor()
        X, y = preprocessor.preprocess(df, is_training=True)

        assert len(X) == len(df)
        assert len(y) == len(df)

        # Step 4: Split data
        X_train, X_test, y_train, y_test = preprocessor.split_data(X, y)

        assert len(X_train) + len(X_test) == len(X)
        assert len(y_train) + len(y_test) == len(y)
