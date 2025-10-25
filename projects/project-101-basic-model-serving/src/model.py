"""
Model loading and inference for ResNet50 image classification.
"""

import logging
import time
from typing import Dict, Any, Optional
import torch
import torch.nn as nn
from torchvision.models import resnet50, ResNet50_Weights

from src.config import settings
from src.utils import (
    load_imagenet_labels,
    preprocess_image,
    format_predictions,
    tensor_to_device,
    ImageProcessingError
)

logger = logging.getLogger(__name__)


class ModelInferenceError(Exception):
    """Custom exception for model inference errors."""
    pass


class ResNetClassifier:
    """
    ResNet50 image classifier with pretrained ImageNet weights.

    This class handles model loading, caching, and inference for image
    classification tasks.

    Attributes:
        model: PyTorch ResNet50 model
        device: Device to run inference on (cpu or cuda)
        labels: List of ImageNet class labels
        is_loaded: Whether the model is loaded and ready
    """

    def __init__(self, device: Optional[str] = None):
        """
        Initialize the ResNet classifier.

        Args:
            device: Device to use for inference ('cpu' or 'cuda').
                   If None, uses settings.model_device
        """
        self.device = device or settings.model_device
        self.model: Optional[nn.Module] = None
        self.labels: list = []
        self.is_loaded: bool = False

        # Validate device availability
        if self.device == "cuda" and not torch.cuda.is_available():
            logger.warning("CUDA requested but not available. Falling back to CPU.")
            self.device = "cpu"

        logger.info(f"Initialized ResNetClassifier with device: {self.device}")

    def load(self) -> None:
        """
        Load the ResNet50 model and ImageNet labels.

        This method downloads the pretrained model weights and loads the
        model into memory. It should be called once at application startup.

        Raises:
            RuntimeError: If model loading fails
        """
        if self.is_loaded:
            logger.warning("Model is already loaded")
            return

        try:
            start_time = time.time()
            logger.info("Loading ResNet50 model...")

            # Load pretrained ResNet50 with recommended weights
            weights = ResNet50_Weights.IMAGENET1K_V2
            self.model = resnet50(weights=weights)

            # Set model to evaluation mode
            self.model.eval()

            # Move model to target device
            self.model = self.model.to(self.device)

            # Load ImageNet labels
            self.labels = load_imagenet_labels()

            self.is_loaded = True
            load_time = time.time() - start_time

            logger.info(
                f"Model loaded successfully in {load_time:.2f}s on device: {self.device}"
            )

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise RuntimeError(f"Model loading failed: {str(e)}")

    def predict(
        self,
        image_tensor: torch.Tensor,
        top_k: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Perform inference on a preprocessed image tensor.

        Args:
            image_tensor: Preprocessed image tensor (1, 3, 224, 224)
            top_k: Number of top predictions to return. If None, uses
                   settings.top_k_predictions

        Returns:
            dict: Prediction results with structure:
                {
                    "predictions": [
                        {"class_id": int, "label": str, "confidence": float},
                        ...
                    ],
                    "inference_time_ms": float
                }

        Raises:
            ModelInferenceError: If inference fails
            RuntimeError: If model is not loaded
        """
        if not self.is_loaded:
            raise RuntimeError("Model is not loaded. Call load() first.")

        if top_k is None:
            top_k = settings.top_k_predictions

        try:
            start_time = time.time()

            # Move tensor to model device
            image_tensor = tensor_to_device(image_tensor, self.device)

            # Perform inference
            with torch.no_grad():
                logits = self.model(image_tensor)
                probabilities = torch.nn.functional.softmax(logits, dim=1)

            # Format predictions
            predictions = format_predictions(
                probabilities,
                self.labels,
                top_k=top_k
            )

            inference_time = (time.time() - start_time) * 1000  # Convert to ms

            logger.debug(f"Inference completed in {inference_time:.2f}ms")

            return {
                "predictions": predictions,
                "inference_time_ms": inference_time
            }

        except Exception as e:
            logger.error(f"Inference failed: {e}")
            raise ModelInferenceError(f"Failed to perform inference: {str(e)}")

    def predict_from_image(
        self,
        image,
        top_k: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Perform inference on a PIL Image.

        This is a convenience method that handles preprocessing.

        Args:
            image: PIL Image object
            top_k: Number of top predictions to return

        Returns:
            dict: Prediction results

        Raises:
            ImageProcessingError: If image preprocessing fails
            ModelInferenceError: If inference fails
        """
        try:
            # Preprocess image
            image_tensor = preprocess_image(image)

            # Perform inference
            result = self.predict(image_tensor, top_k=top_k)

            return result

        except Exception as e:
            if isinstance(e, (ImageProcessingError, ModelInferenceError)):
                raise
            logger.error(f"Prediction from image failed: {e}")
            raise ModelInferenceError(f"Prediction failed: {str(e)}")

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the loaded model.

        Returns:
            dict: Model information including name, device, and status
        """
        info = {
            "model_name": settings.model_name,
            "device": self.device,
            "is_loaded": self.is_loaded,
            "num_classes": len(self.labels) if self.labels else 0,
        }

        if self.device == "cuda" and torch.cuda.is_available():
            info["cuda_device_name"] = torch.cuda.get_device_name(0)
            info["cuda_memory_allocated"] = torch.cuda.memory_allocated(0)
            info["cuda_memory_reserved"] = torch.cuda.memory_reserved(0)

        return info

    def unload(self) -> None:
        """
        Unload the model from memory.

        This method clears the model and labels from memory and performs
        garbage collection. Useful for testing or resource cleanup.
        """
        if not self.is_loaded:
            logger.warning("Model is not loaded")
            return

        logger.info("Unloading model...")

        self.model = None
        self.labels = []
        self.is_loaded = False

        # Clear CUDA cache if using GPU
        if self.device == "cuda" and torch.cuda.is_available():
            torch.cuda.empty_cache()

        logger.info("Model unloaded successfully")


# Global model instance (singleton pattern)
_model_instance: Optional[ResNetClassifier] = None


def get_model() -> ResNetClassifier:
    """
    Get the global model instance (singleton).

    Returns:
        ResNetClassifier: Global model instance

    Raises:
        RuntimeError: If model is not initialized
    """
    global _model_instance

    if _model_instance is None:
        raise RuntimeError(
            "Model not initialized. Call initialize_model() first."
        )

    return _model_instance


def initialize_model(device: Optional[str] = None) -> ResNetClassifier:
    """
    Initialize and load the global model instance.

    This should be called once at application startup.

    Args:
        device: Device to use for inference

    Returns:
        ResNetClassifier: Initialized model instance
    """
    global _model_instance

    if _model_instance is not None:
        logger.warning("Model already initialized")
        return _model_instance

    logger.info("Initializing global model instance...")

    _model_instance = ResNetClassifier(device=device)
    _model_instance.load()

    return _model_instance


def cleanup_model() -> None:
    """
    Clean up the global model instance.

    This should be called at application shutdown.
    """
    global _model_instance

    if _model_instance is not None:
        logger.info("Cleaning up global model instance...")
        _model_instance.unload()
        _model_instance = None
