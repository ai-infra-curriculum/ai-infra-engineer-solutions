"""Data validation module for ensuring data quality."""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import json

from ..common.config import config
from ..common.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationReport:
    """Data validation report."""
    is_valid: bool
    total_rows: int
    total_columns: int
    missing_values: Dict[str, int]
    duplicate_rows: int
    validation_errors: List[str]
    validation_warnings: List[str]
    schema_valid: bool
    data_quality_score: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


class DataValidator:
    """Validates data quality and schema."""

    def __init__(self, expected_schema: Optional[Dict[str, str]] = None):
        """
        Initialize data validator.

        Args:
            expected_schema: Expected schema as {column: dtype} mapping
        """
        self.expected_schema = expected_schema or self._get_default_schema()
        self.errors = []
        self.warnings = []

    def _get_default_schema(self) -> Dict[str, str]:
        """Get default expected schema for churn data."""
        return {
            'tenure': 'numeric',
            'monthly_charges': 'numeric',
            'total_charges': 'numeric',
            'contract_type': 'categorical',
            'payment_method': 'categorical',
            'internet_service': 'categorical',
            'online_security': 'numeric',
            'tech_support': 'numeric',
            'streaming_tv': 'numeric',
            'streaming_movies': 'numeric',
            'paperless_billing': 'numeric',
            'senior_citizen': 'numeric',
            'partner': 'numeric',
            'dependents': 'numeric',
            'multiple_lines': 'numeric',
            'Churn': 'numeric'
        }

    def validate(self, df: pd.DataFrame) -> ValidationReport:
        """
        Validate DataFrame.

        Args:
            df: DataFrame to validate

        Returns:
            ValidationReport with validation results
        """
        logger.info("Starting data validation")
        self.errors = []
        self.warnings = []

        # Basic checks
        total_rows, total_columns = df.shape
        logger.info(f"Validating data with shape: {df.shape}")

        # Check for missing values
        missing_values = self._check_missing_values(df)

        # Check for duplicates
        duplicate_rows = self._check_duplicates(df)

        # Validate schema
        schema_valid = self._validate_schema(df)

        # Check data ranges
        self._check_data_ranges(df)

        # Check target distribution
        self._check_target_distribution(df)

        # Calculate data quality score
        quality_score = self._calculate_quality_score(
            df, missing_values, duplicate_rows
        )

        # Determine overall validity
        is_valid = len(self.errors) == 0 and quality_score >= 0.7

        report = ValidationReport(
            is_valid=is_valid,
            total_rows=total_rows,
            total_columns=total_columns,
            missing_values=missing_values,
            duplicate_rows=duplicate_rows,
            validation_errors=self.errors,
            validation_warnings=self.warnings,
            schema_valid=schema_valid,
            data_quality_score=quality_score
        )

        logger.info(f"Validation complete. Valid: {is_valid}, Quality score: {quality_score:.2f}")
        return report

    def _check_missing_values(self, df: pd.DataFrame) -> Dict[str, int]:
        """Check for missing values."""
        missing = df.isnull().sum().to_dict()
        missing = {k: v for k, v in missing.items() if v > 0}

        if missing:
            total_missing = sum(missing.values())
            pct_missing = (total_missing / (df.shape[0] * df.shape[1])) * 100

            if pct_missing > 10:
                self.errors.append(
                    f"High percentage of missing values: {pct_missing:.2f}%"
                )
            elif pct_missing > 5:
                self.warnings.append(
                    f"Moderate percentage of missing values: {pct_missing:.2f}%"
                )

        return missing

    def _check_duplicates(self, df: pd.DataFrame) -> int:
        """Check for duplicate rows."""
        duplicates = df.duplicated().sum()

        if duplicates > 0:
            pct_duplicates = (duplicates / len(df)) * 100
            if pct_duplicates > 5:
                self.errors.append(
                    f"High percentage of duplicate rows: {pct_duplicates:.2f}%"
                )
            else:
                self.warnings.append(
                    f"Found {duplicates} duplicate rows ({pct_duplicates:.2f}%)"
                )

        return duplicates

    def _validate_schema(self, df: pd.DataFrame) -> bool:
        """Validate DataFrame schema."""
        missing_cols = set(self.expected_schema.keys()) - set(df.columns)
        if missing_cols:
            self.errors.append(f"Missing required columns: {missing_cols}")
            return False

        # Check data types
        for col, expected_type in self.expected_schema.items():
            if col not in df.columns:
                continue

            actual_dtype = df[col].dtype

            if expected_type == 'numeric':
                if not np.issubdtype(actual_dtype, np.number):
                    self.warnings.append(
                        f"Column '{col}' expected to be numeric but is {actual_dtype}"
                    )
            elif expected_type == 'categorical':
                # Categorical can be object or category dtype
                if actual_dtype not in ['object', 'category']:
                    self.warnings.append(
                        f"Column '{col}' expected to be categorical but is {actual_dtype}"
                    )

        return len(missing_cols) == 0

    def _check_data_ranges(self, df: pd.DataFrame):
        """Check if data values are in expected ranges."""
        # Check tenure (should be 0-72 months)
        if 'tenure' in df.columns:
            if df['tenure'].min() < 0 or df['tenure'].max() > 100:
                self.warnings.append(
                    f"Tenure values outside expected range: [{df['tenure'].min()}, {df['tenure'].max()}]"
                )

        # Check monthly charges (should be positive)
        if 'monthly_charges' in df.columns:
            if df['monthly_charges'].min() < 0:
                self.errors.append("Monthly charges contain negative values")

        # Check target variable
        if config.TARGET_COLUMN in df.columns:
            unique_values = df[config.TARGET_COLUMN].unique()
            if not set(unique_values).issubset({0, 1}):
                self.errors.append(
                    f"Target variable contains invalid values: {unique_values}"
                )

    def _check_target_distribution(self, df: pd.DataFrame):
        """Check target variable distribution."""
        if config.TARGET_COLUMN not in df.columns:
            self.errors.append(f"Target column '{config.TARGET_COLUMN}' not found")
            return

        target_dist = df[config.TARGET_COLUMN].value_counts(normalize=True)

        # Check for severe class imbalance
        if len(target_dist) < 2:
            self.errors.append("Target variable has only one class")
        else:
            min_class_ratio = target_dist.min()
            if min_class_ratio < 0.05:
                self.warnings.append(
                    f"Severe class imbalance detected: {target_dist.to_dict()}"
                )
            elif min_class_ratio < 0.2:
                self.warnings.append(
                    f"Class imbalance detected: {target_dist.to_dict()}"
                )

    def _calculate_quality_score(
        self,
        df: pd.DataFrame,
        missing_values: Dict[str, int],
        duplicate_rows: int
    ) -> float:
        """
        Calculate overall data quality score (0-1).

        Args:
            df: DataFrame
            missing_values: Missing values per column
            duplicate_rows: Number of duplicate rows

        Returns:
            Quality score between 0 and 1
        """
        total_cells = df.shape[0] * df.shape[1]

        # Completeness score (1 - missing ratio)
        total_missing = sum(missing_values.values())
        completeness = 1 - (total_missing / total_cells)

        # Uniqueness score (1 - duplicate ratio)
        uniqueness = 1 - (duplicate_rows / len(df))

        # Schema validity score
        schema_score = 1.0 if self._validate_schema(df) else 0.5

        # Weighted average
        quality_score = (
            0.4 * completeness +
            0.3 * uniqueness +
            0.3 * schema_score
        )

        return round(quality_score, 3)
