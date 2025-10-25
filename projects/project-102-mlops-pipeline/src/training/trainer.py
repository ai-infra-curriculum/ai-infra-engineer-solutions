"""Model training module with MLflow integration."""

import mlflow
import mlflow.sklearn
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier
from sklearn.model_selection import cross_val_score

from ..common.config import config
from ..common.logger import get_logger

logger = get_logger(__name__)


class ModelTrainer:
    """Handles model training with MLflow tracking."""

    def __init__(self):
        """Initialize model trainer."""
        self.models_dir = Path(config.MODELS_DIR)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        # Set MLflow tracking URI
        mlflow.set_tracking_uri(config.MLFLOW_TRACKING_URI)
        mlflow.set_experiment(config.MLFLOW_EXPERIMENT_NAME)

        logger.info(f"MLflow tracking URI: {config.MLFLOW_TRACKING_URI}")
        logger.info(f"MLflow experiment: {config.MLFLOW_EXPERIMENT_NAME}")

    def get_model_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        Get model configurations to train.

        Returns:
            Dictionary of model configurations
        """
        return {
            'logistic_regression': {
                'model_class': LogisticRegression,
                'params': {
                    'max_iter': 1000,
                    'random_state': config.RANDOM_STATE,
                    'n_jobs': -1
                },
                'tuning_params': {
                    'C': [0.1, 1.0, 10.0],
                    'solver': ['lbfgs', 'liblinear']
                }
            },
            'random_forest': {
                'model_class': RandomForestClassifier,
                'params': {
                    'random_state': config.RANDOM_STATE,
                    'n_jobs': -1
                },
                'tuning_params': {
                    'n_estimators': [100, 200],
                    'max_depth': [10, 20, None],
                    'min_samples_split': [2, 5]
                }
            },
            'gradient_boosting': {
                'model_class': GradientBoostingClassifier,
                'params': {
                    'random_state': config.RANDOM_STATE
                },
                'tuning_params': {
                    'n_estimators': [100, 200],
                    'learning_rate': [0.01, 0.1],
                    'max_depth': [3, 5]
                }
            },
            'xgboost': {
                'model_class': XGBClassifier,
                'params': {
                    'random_state': config.RANDOM_STATE,
                    'n_jobs': -1,
                    'eval_metric': 'logloss'
                },
                'tuning_params': {
                    'n_estimators': [100, 200],
                    'learning_rate': [0.01, 0.1],
                    'max_depth': [3, 5, 7]
                }
            }
        }

    def train_model(
        self,
        model_name: str,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        params: Optional[Dict[str, Any]] = None
    ) -> tuple:
        """
        Train a single model with MLflow tracking.

        Args:
            model_name: Name of the model
            X_train: Training features
            y_train: Training target
            X_test: Test features
            y_test: Test target
            params: Model parameters (optional)

        Returns:
            Tuple of (trained model, run_id)
        """
        logger.info(f"Training {model_name}")

        # Get model configuration
        model_configs = self.get_model_configs()
        if model_name not in model_configs:
            raise ValueError(f"Unknown model: {model_name}")

        model_config = model_configs[model_name]
        model_class = model_config['model_class']
        default_params = model_config['params']

        # Merge with provided parameters
        if params:
            default_params.update(params)

        # Start MLflow run
        with mlflow.start_run(run_name=model_name) as run:
            # Log parameters
            mlflow.log_params(default_params)
            mlflow.log_param('model_type', model_name)

            # Train model
            model = model_class(**default_params)
            model.fit(X_train, y_train)

            # Perform cross-validation
            cv_scores = cross_val_score(
                model, X_train, y_train,
                cv=config.CV_FOLDS,
                scoring='f1',
                n_jobs=-1
            )

            # Log cross-validation metrics
            mlflow.log_metric('cv_f1_mean', cv_scores.mean())
            mlflow.log_metric('cv_f1_std', cv_scores.std())

            # Make predictions
            y_train_pred = model.predict(X_train)
            y_test_pred = model.predict(X_test)

            # Get prediction probabilities
            y_train_proba = model.predict_proba(X_train)[:, 1]
            y_test_proba = model.predict_proba(X_test)[:, 1]

            # Calculate and log metrics
            from sklearn.metrics import (
                accuracy_score, precision_score, recall_score,
                f1_score, roc_auc_score, confusion_matrix
            )

            train_metrics = {
                'train_accuracy': accuracy_score(y_train, y_train_pred),
                'train_precision': precision_score(y_train, y_train_pred),
                'train_recall': recall_score(y_train, y_train_pred),
                'train_f1': f1_score(y_train, y_train_pred),
                'train_roc_auc': roc_auc_score(y_train, y_train_proba)
            }

            test_metrics = {
                'test_accuracy': accuracy_score(y_test, y_test_pred),
                'test_precision': precision_score(y_test, y_test_pred),
                'test_recall': recall_score(y_test, y_test_pred),
                'test_f1': f1_score(y_test, y_test_pred),
                'test_roc_auc': roc_auc_score(y_test, y_test_proba)
            }

            # Log all metrics
            mlflow.log_metrics(train_metrics)
            mlflow.log_metrics(test_metrics)

            # Log confusion matrix
            cm = confusion_matrix(y_test, y_test_pred)
            mlflow.log_text(str(cm), 'confusion_matrix.txt')

            # Log feature importance if available
            if hasattr(model, 'feature_importances_'):
                feature_importance = pd.DataFrame({
                    'feature': X_train.columns,
                    'importance': model.feature_importances_
                }).sort_values('importance', ascending=False)

                mlflow.log_text(
                    feature_importance.to_string(),
                    'feature_importance.txt'
                )

            # Log model
            mlflow.sklearn.log_model(
                model,
                'model',
                registered_model_name=config.MODEL_NAME
            )

            # Log dataset information
            mlflow.log_param('train_samples', len(X_train))
            mlflow.log_param('test_samples', len(X_test))
            mlflow.log_param('n_features', X_train.shape[1])

            logger.info(f"Training complete. Test F1: {test_metrics['test_f1']:.4f}")

            return model, run.info.run_id

    def train_all_models(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series
    ) -> Dict[str, tuple]:
        """
        Train all configured models.

        Args:
            X_train: Training features
            y_train: Training target
            X_test: Test features
            y_test: Test target

        Returns:
            Dictionary of {model_name: (model, run_id)}
        """
        logger.info("Training all models")

        results = {}
        model_configs = self.get_model_configs()

        for model_name in model_configs.keys():
            try:
                model, run_id = self.train_model(
                    model_name, X_train, y_train, X_test, y_test
                )
                results[model_name] = (model, run_id)
            except Exception as e:
                logger.error(f"Failed to train {model_name}: {e}")

        logger.info(f"Successfully trained {len(results)} models")
        return results

    def hyperparameter_tuning(
        self,
        model_name: str,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        n_iter: int = 10
    ) -> tuple:
        """
        Perform hyperparameter tuning using RandomizedSearchCV.

        Args:
            model_name: Name of the model
            X_train: Training features
            y_train: Training target
            X_test: Test features
            y_test: Test target
            n_iter: Number of parameter settings to sample

        Returns:
            Tuple of (best model, run_id)
        """
        logger.info(f"Hyperparameter tuning for {model_name}")

        from sklearn.model_selection import RandomizedSearchCV

        # Get model configuration
        model_configs = self.get_model_configs()
        if model_name not in model_configs:
            raise ValueError(f"Unknown model: {model_name}")

        model_config = model_configs[model_name]
        model_class = model_config['model_class']
        base_params = model_config['params']
        tuning_params = model_config['tuning_params']

        # Create base model
        base_model = model_class(**base_params)

        # Perform randomized search
        random_search = RandomizedSearchCV(
            base_model,
            tuning_params,
            n_iter=n_iter,
            cv=config.CV_FOLDS,
            scoring='f1',
            n_jobs=-1,
            random_state=config.RANDOM_STATE,
            verbose=1
        )

        # Start MLflow run
        with mlflow.start_run(run_name=f"{model_name}_tuned") as run:
            # Fit random search
            random_search.fit(X_train, y_train)

            # Get best model
            best_model = random_search.best_estimator_
            best_params = random_search.best_params_

            logger.info(f"Best parameters: {best_params}")

            # Log best parameters
            mlflow.log_params(best_params)
            mlflow.log_param('model_type', f"{model_name}_tuned")
            mlflow.log_metric('best_cv_score', random_search.best_score_)

            # Evaluate on test set
            y_test_pred = best_model.predict(X_test)
            y_test_proba = best_model.predict_proba(X_test)[:, 1]

            from sklearn.metrics import (
                accuracy_score, precision_score, recall_score,
                f1_score, roc_auc_score
            )

            test_metrics = {
                'test_accuracy': accuracy_score(y_test, y_test_pred),
                'test_precision': precision_score(y_test, y_test_pred),
                'test_recall': recall_score(y_test, y_test_pred),
                'test_f1': f1_score(y_test, y_test_pred),
                'test_roc_auc': roc_auc_score(y_test, y_test_proba)
            }

            mlflow.log_metrics(test_metrics)

            # Log model
            mlflow.sklearn.log_model(
                best_model,
                'model',
                registered_model_name=config.MODEL_NAME
            )

            logger.info(f"Tuning complete. Test F1: {test_metrics['test_f1']:.4f}")

            return best_model, run.info.run_id
