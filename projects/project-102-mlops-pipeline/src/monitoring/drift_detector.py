"""Data and model drift detection."""

import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple
from scipy import stats
from sklearn.metrics import jensen_shannon_distance

from ..common.config import config
from ..common.logger import get_logger

logger = get_logger(__name__)


class DriftDetector:
    """Detects data drift and model drift."""

    def __init__(self, threshold: float = None):
        """
        Initialize drift detector.

        Args:
            threshold: Drift threshold (0-1)
        """
        self.threshold = threshold or config.DRIFT_THRESHOLD
        self.reference_data = None
        self.reference_predictions = None

    def set_reference_data(
        self,
        data: pd.DataFrame,
        predictions: np.ndarray = None
    ):
        """
        Set reference data for drift detection.

        Args:
            data: Reference feature data
            predictions: Reference predictions (optional)
        """
        self.reference_data = data
        self.reference_predictions = predictions
        logger.info(f"Set reference data with {len(data)} samples")

    def detect_feature_drift(
        self,
        current_data: pd.DataFrame,
        method: str = 'ks'
    ) -> Dict[str, Any]:
        """
        Detect drift in feature distributions.

        Args:
            current_data: Current feature data
            method: Drift detection method ('ks' or 'js')

        Returns:
            Dictionary with drift detection results
        """
        if self.reference_data is None:
            raise ValueError("Reference data not set. Call set_reference_data first.")

        logger.info(f"Detecting feature drift using {method} method")

        drift_results = {}
        drifted_features = []

        for column in self.reference_data.columns:
            if column not in current_data.columns:
                logger.warning(f"Column {column} not found in current data")
                continue

            if method == 'ks':
                drift_score = self._kolmogorov_smirnov_test(
                    self.reference_data[column],
                    current_data[column]
                )
            elif method == 'js':
                drift_score = self._jensen_shannon_divergence(
                    self.reference_data[column],
                    current_data[column]
                )
            else:
                raise ValueError(f"Unknown method: {method}")

            is_drifted = drift_score > self.threshold

            drift_results[column] = {
                'drift_score': drift_score,
                'is_drifted': is_drifted,
                'method': method
            }

            if is_drifted:
                drifted_features.append(column)
                logger.warning(
                    f"Drift detected in feature '{column}': score={drift_score:.4f}"
                )

        overall_drift = len(drifted_features) > 0

        summary = {
            'overall_drift_detected': overall_drift,
            'num_drifted_features': len(drifted_features),
            'drifted_features': drifted_features,
            'total_features': len(drift_results),
            'drift_percentage': (len(drifted_features) / len(drift_results)) * 100,
            'feature_drift_scores': drift_results
        }

        logger.info(
            f"Feature drift detection complete. "
            f"{len(drifted_features)}/{len(drift_results)} features drifted"
        )

        return summary

    def detect_prediction_drift(
        self,
        current_predictions: np.ndarray
    ) -> Dict[str, Any]:
        """
        Detect drift in prediction distributions.

        Args:
            current_predictions: Current model predictions

        Returns:
            Dictionary with drift detection results
        """
        if self.reference_predictions is None:
            raise ValueError(
                "Reference predictions not set. Call set_reference_data first."
            )

        logger.info("Detecting prediction drift")

        # For binary classification
        if len(np.unique(current_predictions)) <= 2:
            # Compare class distributions
            ref_dist = np.bincount(self.reference_predictions.astype(int)) / len(
                self.reference_predictions
            )
            curr_dist = np.bincount(current_predictions.astype(int)) / len(
                current_predictions
            )

            # Pad to same length
            max_len = max(len(ref_dist), len(curr_dist))
            ref_dist = np.pad(ref_dist, (0, max_len - len(ref_dist)))
            curr_dist = np.pad(curr_dist, (0, max_len - len(curr_dist)))

            # Calculate divergence
            drift_score = jensen_shannon_distance(ref_dist, curr_dist)
        else:
            # For continuous predictions, use KS test
            statistic, p_value = stats.ks_2samp(
                self.reference_predictions,
                current_predictions
            )
            drift_score = statistic

        is_drifted = drift_score > self.threshold

        result = {
            'drift_score': float(drift_score),
            'is_drifted': is_drifted,
            'threshold': self.threshold,
            'reference_mean': float(np.mean(self.reference_predictions)),
            'current_mean': float(np.mean(current_predictions)),
            'reference_std': float(np.std(self.reference_predictions)),
            'current_std': float(np.std(current_predictions))
        }

        if is_drifted:
            logger.warning(f"Prediction drift detected: score={drift_score:.4f}")
        else:
            logger.info("No prediction drift detected")

        return result

    def _kolmogorov_smirnov_test(
        self,
        reference: pd.Series,
        current: pd.Series
    ) -> float:
        """
        Perform Kolmogorov-Smirnov test.

        Args:
            reference: Reference distribution
            current: Current distribution

        Returns:
            KS statistic (0-1)
        """
        # Handle missing values
        reference = reference.dropna()
        current = current.dropna()

        if len(reference) == 0 or len(current) == 0:
            return 0.0

        # For categorical data, compare frequencies
        if reference.dtype == 'object' or reference.dtype.name == 'category':
            ref_freq = reference.value_counts(normalize=True)
            curr_freq = current.value_counts(normalize=True)

            # Align indices
            all_categories = set(ref_freq.index) | set(curr_freq.index)
            ref_freq = ref_freq.reindex(all_categories, fill_value=0)
            curr_freq = curr_freq.reindex(all_categories, fill_value=0)

            # Calculate max difference
            return float(np.max(np.abs(ref_freq - curr_freq)))

        # For numerical data, use KS test
        statistic, p_value = stats.ks_2samp(reference, current)
        return statistic

    def _jensen_shannon_divergence(
        self,
        reference: pd.Series,
        current: pd.Series
    ) -> float:
        """
        Calculate Jensen-Shannon divergence.

        Args:
            reference: Reference distribution
            current: Current distribution

        Returns:
            JS divergence (0-1)
        """
        # Handle missing values
        reference = reference.dropna()
        current = current.dropna()

        if len(reference) == 0 or len(current) == 0:
            return 0.0

        # Create histograms
        if reference.dtype == 'object' or reference.dtype.name == 'category':
            # For categorical
            ref_freq = reference.value_counts(normalize=True)
            curr_freq = current.value_counts(normalize=True)

            # Align indices
            all_categories = set(ref_freq.index) | set(curr_freq.index)
            ref_dist = ref_freq.reindex(all_categories, fill_value=1e-10)
            curr_dist = curr_freq.reindex(all_categories, fill_value=1e-10)

            return jensen_shannon_distance(ref_dist, curr_dist)
        else:
            # For numerical
            min_val = min(reference.min(), current.min())
            max_val = max(reference.max(), current.max())
            bins = np.linspace(min_val, max_val, 30)

            ref_hist, _ = np.histogram(reference, bins=bins, density=True)
            curr_hist, _ = np.histogram(current, bins=bins, density=True)

            # Normalize
            ref_hist = ref_hist / (ref_hist.sum() + 1e-10)
            curr_hist = curr_hist / (curr_hist.sum() + 1e-10)

            # Add small epsilon to avoid log(0)
            ref_hist = ref_hist + 1e-10
            curr_hist = curr_hist + 1e-10

            return jensen_shannon_distance(ref_hist, curr_hist)

    def monitor_drift(
        self,
        current_data: pd.DataFrame,
        current_predictions: np.ndarray = None
    ) -> Dict[str, Any]:
        """
        Monitor both feature and prediction drift.

        Args:
            current_data: Current feature data
            current_predictions: Current predictions (optional)

        Returns:
            Combined drift detection results
        """
        logger.info("Running comprehensive drift monitoring")

        results = {
            'timestamp': pd.Timestamp.now().isoformat(),
            'feature_drift': self.detect_feature_drift(current_data),
        }

        if current_predictions is not None:
            results['prediction_drift'] = self.detect_prediction_drift(
                current_predictions
            )

        # Overall drift status
        feature_drift = results['feature_drift']['overall_drift_detected']
        prediction_drift = (
            results.get('prediction_drift', {}).get('is_drifted', False)
        )

        results['overall_drift_detected'] = feature_drift or prediction_drift

        if results['overall_drift_detected']:
            logger.warning("DRIFT ALERT: Data or model drift detected!")
        else:
            logger.info("No drift detected")

        return results
