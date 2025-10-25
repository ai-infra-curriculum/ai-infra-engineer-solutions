"""Unit tests for data validation module."""

import pytest
import pandas as pd
import numpy as np

import sys
sys.path.insert(0, '/opt/airflow')

from src.data.validation import DataValidator, ValidationReport


class TestDataValidator:
    """Test DataValidator class."""

    def test_validate_good_data(self, sample_data):
        """Test validation with good data."""
        validator = DataValidator()
        report = validator.validate(sample_data)

        assert isinstance(report, ValidationReport)
        assert report.is_valid
        assert report.total_rows == len(sample_data)
        assert report.total_columns == len(sample_data.columns)
        assert report.data_quality_score > 0.7

    def test_validate_data_with_missing_values(self, sample_data):
        """Test validation with missing values."""
        # Add missing values
        data_with_na = sample_data.copy()
        data_with_na.loc[:10, 'tenure'] = np.nan

        validator = DataValidator()
        report = validator.validate(data_with_na)

        assert 'tenure' in report.missing_values
        assert report.missing_values['tenure'] > 0

    def test_validate_data_with_duplicates(self, sample_data):
        """Test validation with duplicate rows."""
        # Add duplicates
        data_with_dupes = pd.concat([sample_data, sample_data.head(10)])

        validator = DataValidator()
        report = validator.validate(data_with_dupes)

        assert report.duplicate_rows > 0

    def test_schema_validation(self, sample_data):
        """Test schema validation."""
        validator = DataValidator()

        # Valid schema
        report = validator.validate(sample_data)
        assert report.schema_valid

        # Invalid schema (missing column)
        invalid_data = sample_data.drop(columns=['Churn'])
        report = validator.validate(invalid_data)
        assert not report.schema_valid

    def test_target_distribution_check(self, sample_data):
        """Test target distribution check."""
        validator = DataValidator()

        # Normal distribution
        report = validator.validate(sample_data)
        assert len(report.validation_errors) == 0

        # Single class
        imbalanced_data = sample_data.copy()
        imbalanced_data['Churn'] = 0
        report = validator.validate(imbalanced_data)
        assert len(report.validation_errors) > 0

    def test_quality_score_calculation(self, sample_data):
        """Test quality score calculation."""
        validator = DataValidator()

        # Perfect data
        report = validator.validate(sample_data)
        assert report.data_quality_score > 0.9

        # Data with issues
        bad_data = sample_data.copy()
        bad_data.loc[:100, 'tenure'] = np.nan
        bad_data = pd.concat([bad_data, bad_data.head(50)])

        report = validator.validate(bad_data)
        assert report.data_quality_score < 0.9

    def test_report_serialization(self, sample_data):
        """Test report serialization."""
        validator = DataValidator()
        report = validator.validate(sample_data)

        # Test to_dict
        report_dict = report.to_dict()
        assert isinstance(report_dict, dict)
        assert 'is_valid' in report_dict

        # Test to_json
        report_json = report.to_json()
        assert isinstance(report_json, str)
        assert 'is_valid' in report_json
