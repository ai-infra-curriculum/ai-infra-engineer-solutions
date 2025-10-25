"""Data preprocessing module for feature engineering and transformation."""

import pandas as pd
import numpy as np
from typing import Tuple, List, Optional
from pathlib import Path
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
import joblib

from ..common.config import config
from ..common.logger import get_logger

logger = get_logger(__name__)


class DataPreprocessor:
    """Handles data preprocessing and feature engineering."""

    def __init__(self):
        """Initialize data preprocessor."""
        self.scaler = StandardScaler()
        self.label_encoders = {}
        self.categorical_columns = []
        self.numerical_columns = []
        self.processed_data_path = Path(config.PROCESSED_DATA_PATH)
        self.processed_data_path.mkdir(parents=True, exist_ok=True)

    def preprocess(
        self,
        df: pd.DataFrame,
        is_training: bool = True
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Preprocess data for training or inference.

        Args:
            df: Input DataFrame
            is_training: Whether this is training data

        Returns:
            Tuple of (features DataFrame, target Series)
        """
        logger.info(f"Preprocessing data with shape: {df.shape}")

        # Make a copy
        df = df.copy()

        # Handle missing values
        df = self._handle_missing_values(df)

        # Separate features and target
        if config.TARGET_COLUMN in df.columns:
            target = df[config.TARGET_COLUMN]
            features = df.drop(columns=[config.TARGET_COLUMN])
        else:
            target = None
            features = df

        # Identify column types
        if is_training:
            self._identify_column_types(features)

        # Engineer features
        features = self._engineer_features(features)

        # Encode categorical variables
        features = self._encode_categorical(features, is_training)

        # Scale numerical features
        features = self._scale_numerical(features, is_training)

        logger.info(f"Preprocessing complete. Output shape: {features.shape}")

        return features, target

    def _handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """Handle missing values in the dataset."""
        logger.info("Handling missing values")

        # For numerical columns, fill with median
        numerical_cols = df.select_dtypes(include=[np.number]).columns
        for col in numerical_cols:
            if df[col].isnull().sum() > 0:
                median_val = df[col].median()
                df[col].fillna(median_val, inplace=True)
                logger.info(f"Filled {col} missing values with median: {median_val}")

        # For categorical columns, fill with mode
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns
        for col in categorical_cols:
            if df[col].isnull().sum() > 0:
                mode_val = df[col].mode()[0]
                df[col].fillna(mode_val, inplace=True)
                logger.info(f"Filled {col} missing values with mode: {mode_val}")

        return df

    def _identify_column_types(self, df: pd.DataFrame):
        """Identify categorical and numerical columns."""
        self.categorical_columns = df.select_dtypes(
            include=['object', 'category']
        ).columns.tolist()

        self.numerical_columns = df.select_dtypes(
            include=[np.number]
        ).columns.tolist()

        logger.info(f"Identified {len(self.categorical_columns)} categorical columns")
        logger.info(f"Identified {len(self.numerical_columns)} numerical columns")

    def _engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Engineer new features from existing ones."""
        logger.info("Engineering features")

        # Create tenure groups
        if 'tenure' in df.columns:
            df['tenure_group'] = pd.cut(
                df['tenure'],
                bins=[0, 12, 24, 48, 72],
                labels=['0-1yr', '1-2yr', '2-4yr', '4yr+']
            )

        # Create charge ratio feature
        if 'monthly_charges' in df.columns and 'total_charges' in df.columns:
            df['charge_ratio'] = df['monthly_charges'] / (df['total_charges'] + 1)

        # Create service usage score
        service_cols = [
            'online_security', 'tech_support', 'streaming_tv', 'streaming_movies'
        ]
        available_service_cols = [col for col in service_cols if col in df.columns]
        if available_service_cols:
            df['service_usage_score'] = df[available_service_cols].sum(axis=1)

        return df

    def _encode_categorical(
        self,
        df: pd.DataFrame,
        is_training: bool
    ) -> pd.DataFrame:
        """Encode categorical variables."""
        logger.info("Encoding categorical variables")

        for col in self.categorical_columns:
            if col not in df.columns:
                continue

            if is_training:
                # Create and fit label encoder
                le = LabelEncoder()
                df[col] = le.fit_transform(df[col].astype(str))
                self.label_encoders[col] = le
                logger.info(f"Encoded {col} with {len(le.classes_)} classes")
            else:
                # Use existing label encoder
                if col in self.label_encoders:
                    le = self.label_encoders[col]
                    # Handle unseen categories
                    df[col] = df[col].astype(str).apply(
                        lambda x: x if x in le.classes_ else le.classes_[0]
                    )
                    df[col] = le.transform(df[col])

        return df

    def _scale_numerical(
        self,
        df: pd.DataFrame,
        is_training: bool
    ) -> pd.DataFrame:
        """Scale numerical features."""
        logger.info("Scaling numerical features")

        numerical_cols = [col for col in self.numerical_columns if col in df.columns]

        if not numerical_cols:
            return df

        if is_training:
            df[numerical_cols] = self.scaler.fit_transform(df[numerical_cols])
            logger.info(f"Fitted scaler on {len(numerical_cols)} numerical columns")
        else:
            df[numerical_cols] = self.scaler.transform(df[numerical_cols])

        return df

    def split_data(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        test_size: float = None,
        random_state: int = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
        """
        Split data into training and test sets.

        Args:
            X: Features
            y: Target
            test_size: Test set size ratio
            random_state: Random state for reproducibility

        Returns:
            Tuple of (X_train, X_test, y_train, y_test)
        """
        if test_size is None:
            test_size = config.TRAIN_TEST_SPLIT
        if random_state is None:
            random_state = config.RANDOM_STATE

        logger.info(f"Splitting data with test_size={test_size}")

        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size=test_size,
            random_state=random_state,
            stratify=y
        )

        logger.info(f"Train set size: {len(X_train)}, Test set size: {len(X_test)}")

        return X_train, X_test, y_train, y_test

    def save_preprocessor(self, filename: str = 'preprocessor.pkl'):
        """Save preprocessor objects."""
        preprocessor_path = self.processed_data_path / filename

        preprocessor_data = {
            'scaler': self.scaler,
            'label_encoders': self.label_encoders,
            'categorical_columns': self.categorical_columns,
            'numerical_columns': self.numerical_columns
        }

        joblib.dump(preprocessor_data, preprocessor_path)
        logger.info(f"Saved preprocessor to {preprocessor_path}")

        return str(preprocessor_path)

    def load_preprocessor(self, filename: str = 'preprocessor.pkl'):
        """Load preprocessor objects."""
        preprocessor_path = self.processed_data_path / filename

        preprocessor_data = joblib.load(preprocessor_path)

        self.scaler = preprocessor_data['scaler']
        self.label_encoders = preprocessor_data['label_encoders']
        self.categorical_columns = preprocessor_data['categorical_columns']
        self.numerical_columns = preprocessor_data['numerical_columns']

        logger.info(f"Loaded preprocessor from {preprocessor_path}")

    def save_processed_data(
        self,
        X_train: pd.DataFrame,
        X_test: pd.DataFrame,
        y_train: pd.Series,
        y_test: pd.Series
    ) -> dict:
        """Save processed data to disk."""
        paths = {
            'X_train': self.processed_data_path / 'X_train.csv',
            'X_test': self.processed_data_path / 'X_test.csv',
            'y_train': self.processed_data_path / 'y_train.csv',
            'y_test': self.processed_data_path / 'y_test.csv'
        }

        X_train.to_csv(paths['X_train'], index=False)
        X_test.to_csv(paths['X_test'], index=False)
        y_train.to_csv(paths['y_train'], index=False, header=['Churn'])
        y_test.to_csv(paths['y_test'], index=False, header=['Churn'])

        logger.info(f"Saved processed data to {self.processed_data_path}")

        return {k: str(v) for k, v in paths.items()}
