"""Model evaluation module."""

import mlflow
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, roc_curve, confusion_matrix, classification_report
)
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

from ..common.config import config
from ..common.logger import get_logger

logger = get_logger(__name__)


class ModelEvaluator:
    """Evaluates model performance and generates reports."""

    def __init__(self):
        """Initialize model evaluator."""
        self.models_dir = Path(config.MODELS_DIR)
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def evaluate_model(
        self,
        model: Any,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        model_name: str = 'model'
    ) -> Dict[str, float]:
        """
        Evaluate model performance.

        Args:
            model: Trained model
            X_test: Test features
            y_test: Test target
            model_name: Name of the model

        Returns:
            Dictionary of metrics
        """
        logger.info(f"Evaluating {model_name}")

        # Make predictions
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1]

        # Calculate metrics
        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, zero_division=0),
            'recall': recall_score(y_test, y_pred, zero_division=0),
            'f1_score': f1_score(y_test, y_pred, zero_division=0),
            'roc_auc': roc_auc_score(y_test, y_proba)
        }

        logger.info(f"Evaluation metrics for {model_name}:")
        for metric, value in metrics.items():
            logger.info(f"  {metric}: {value:.4f}")

        return metrics

    def compare_models(
        self,
        models: Dict[str, Any],
        X_test: pd.DataFrame,
        y_test: pd.Series
    ) -> pd.DataFrame:
        """
        Compare multiple models.

        Args:
            models: Dictionary of {model_name: model}
            X_test: Test features
            y_test: Test target

        Returns:
            DataFrame with comparison results
        """
        logger.info(f"Comparing {len(models)} models")

        results = []
        for model_name, model in models.items():
            metrics = self.evaluate_model(model, X_test, y_test, model_name)
            metrics['model'] = model_name
            results.append(metrics)

        comparison_df = pd.DataFrame(results)
        comparison_df = comparison_df.sort_values('f1_score', ascending=False)

        logger.info("Model comparison:")
        logger.info(f"\n{comparison_df.to_string()}")

        return comparison_df

    def check_model_thresholds(self, metrics: Dict[str, float]) -> tuple:
        """
        Check if model meets minimum performance thresholds.

        Args:
            metrics: Dictionary of metrics

        Returns:
            Tuple of (meets_thresholds: bool, failed_metrics: list)
        """
        thresholds = {
            'accuracy': config.MIN_ACCURACY,
            'precision': config.MIN_PRECISION,
            'recall': config.MIN_RECALL,
            'f1_score': config.MIN_F1_SCORE
        }

        failed_metrics = []
        for metric, threshold in thresholds.items():
            if metric in metrics and metrics[metric] < threshold:
                failed_metrics.append(
                    f"{metric}: {metrics[metric]:.4f} < {threshold:.4f}"
                )

        meets_thresholds = len(failed_metrics) == 0

        if meets_thresholds:
            logger.info("Model meets all performance thresholds")
        else:
            logger.warning(f"Model failed thresholds: {failed_metrics}")

        return meets_thresholds, failed_metrics

    def generate_confusion_matrix_plot(
        self,
        y_test: pd.Series,
        y_pred: np.ndarray,
        save_path: Optional[str] = None
    ) -> str:
        """
        Generate confusion matrix plot.

        Args:
            y_test: True labels
            y_pred: Predicted labels
            save_path: Path to save plot

        Returns:
            Path to saved plot
        """
        cm = confusion_matrix(y_test, y_pred)

        plt.figure(figsize=(8, 6))
        sns.heatmap(
            cm,
            annot=True,
            fmt='d',
            cmap='Blues',
            xticklabels=['No Churn', 'Churn'],
            yticklabels=['No Churn', 'Churn']
        )
        plt.title('Confusion Matrix')
        plt.ylabel('True Label')
        plt.xlabel('Predicted Label')

        if save_path is None:
            save_path = self.models_dir / 'confusion_matrix.png'

        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()

        logger.info(f"Saved confusion matrix plot to {save_path}")
        return str(save_path)

    def generate_roc_curve_plot(
        self,
        y_test: pd.Series,
        y_proba: np.ndarray,
        save_path: Optional[str] = None
    ) -> str:
        """
        Generate ROC curve plot.

        Args:
            y_test: True labels
            y_proba: Predicted probabilities
            save_path: Path to save plot

        Returns:
            Path to saved plot
        """
        fpr, tpr, thresholds = roc_curve(y_test, y_proba)
        roc_auc = roc_auc_score(y_test, y_proba)

        plt.figure(figsize=(8, 6))
        plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC curve (AUC = {roc_auc:.2f})')
        plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--', label='Random')
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('Receiver Operating Characteristic (ROC) Curve')
        plt.legend(loc='lower right')
        plt.grid(True, alpha=0.3)

        if save_path is None:
            save_path = self.models_dir / 'roc_curve.png'

        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()

        logger.info(f"Saved ROC curve plot to {save_path}")
        return str(save_path)

    def generate_feature_importance_plot(
        self,
        model: Any,
        feature_names: list,
        save_path: Optional[str] = None,
        top_n: int = 15
    ) -> Optional[str]:
        """
        Generate feature importance plot.

        Args:
            model: Trained model
            feature_names: List of feature names
            save_path: Path to save plot
            top_n: Number of top features to show

        Returns:
            Path to saved plot or None if not available
        """
        if not hasattr(model, 'feature_importances_'):
            logger.warning("Model does not have feature_importances_ attribute")
            return None

        feature_importance = pd.DataFrame({
            'feature': feature_names,
            'importance': model.feature_importances_
        }).sort_values('importance', ascending=False).head(top_n)

        plt.figure(figsize=(10, 8))
        plt.barh(range(len(feature_importance)), feature_importance['importance'])
        plt.yticks(range(len(feature_importance)), feature_importance['feature'])
        plt.xlabel('Importance')
        plt.title(f'Top {top_n} Feature Importances')
        plt.gca().invert_yaxis()
        plt.tight_layout()

        if save_path is None:
            save_path = self.models_dir / 'feature_importance.png'

        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()

        logger.info(f"Saved feature importance plot to {save_path}")
        return str(save_path)

    def generate_classification_report(
        self,
        y_test: pd.Series,
        y_pred: np.ndarray,
        save_path: Optional[str] = None
    ) -> str:
        """
        Generate classification report.

        Args:
            y_test: True labels
            y_pred: Predicted labels
            save_path: Path to save report

        Returns:
            Path to saved report
        """
        report = classification_report(
            y_test,
            y_pred,
            target_names=['No Churn', 'Churn']
        )

        logger.info(f"Classification Report:\n{report}")

        if save_path is None:
            save_path = self.models_dir / 'classification_report.txt'

        with open(save_path, 'w') as f:
            f.write(report)

        logger.info(f"Saved classification report to {save_path}")
        return str(save_path)

    def generate_evaluation_report(
        self,
        model: Any,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        model_name: str = 'model'
    ) -> Dict[str, Any]:
        """
        Generate comprehensive evaluation report.

        Args:
            model: Trained model
            X_test: Test features
            y_test: Test target
            model_name: Name of the model

        Returns:
            Dictionary with metrics and paths to generated artifacts
        """
        logger.info(f"Generating evaluation report for {model_name}")

        # Make predictions
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1]

        # Calculate metrics
        metrics = self.evaluate_model(model, X_test, y_test, model_name)

        # Generate plots
        cm_path = self.generate_confusion_matrix_plot(y_test, y_pred)
        roc_path = self.generate_roc_curve_plot(y_test, y_proba)
        fi_path = self.generate_feature_importance_plot(model, X_test.columns.tolist())
        report_path = self.generate_classification_report(y_test, y_pred)

        # Check thresholds
        meets_thresholds, failed_metrics = self.check_model_thresholds(metrics)

        report = {
            'model_name': model_name,
            'metrics': metrics,
            'meets_thresholds': meets_thresholds,
            'failed_metrics': failed_metrics,
            'artifacts': {
                'confusion_matrix': cm_path,
                'roc_curve': roc_path,
                'feature_importance': fi_path,
                'classification_report': report_path
            }
        }

        logger.info("Evaluation report generated successfully")
        return report
