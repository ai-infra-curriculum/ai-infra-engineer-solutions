"""
Tests for model loading and inference.
"""

import pytest
import torch
from unittest.mock import patch, Mock

from src.model import (
    ResNetClassifier,
    ModelInferenceError,
    get_model,
    initialize_model,
    cleanup_model,
    _model_instance
)


class TestResNetClassifier:
    """Tests for ResNetClassifier class."""

    def test_init(self):
        """Test model initialization."""
        model = ResNetClassifier(device="cpu")

        assert model.device == "cpu"
        assert model.model is None
        assert model.is_loaded is False
        assert len(model.labels) == 0

    def test_init_cuda_fallback(self):
        """Test CUDA fallback to CPU when CUDA unavailable."""
        with patch("torch.cuda.is_available", return_value=False):
            model = ResNetClassifier(device="cuda")

            # Should fall back to CPU
            assert model.device == "cpu"

    def test_load(self, model_instance):
        """Test model loading."""
        model_instance.load()

        assert model_instance.is_loaded is True
        assert model_instance.model is not None
        assert len(model_instance.labels) == 1000

    def test_load_already_loaded(self, loaded_model):
        """Test loading an already loaded model."""
        # Should not raise exception, just log warning
        loaded_model.load()
        assert loaded_model.is_loaded is True

    def test_predict_not_loaded(self, model_instance, sample_image):
        """Test prediction when model is not loaded."""
        from src.utils import preprocess_image

        tensor = preprocess_image(sample_image)

        with pytest.raises(RuntimeError, match="Model is not loaded"):
            model_instance.predict(tensor)

    def test_predict(self, loaded_model, sample_image):
        """Test model prediction."""
        from src.utils import preprocess_image

        tensor = preprocess_image(sample_image)
        result = loaded_model.predict(tensor, top_k=5)

        assert "predictions" in result
        assert "inference_time_ms" in result
        assert len(result["predictions"]) == 5

        # Check prediction structure
        pred = result["predictions"][0]
        assert "class_id" in pred
        assert "label" in pred
        assert "confidence" in pred
        assert 0 <= pred["confidence"] <= 1

    def test_predict_custom_top_k(self, loaded_model, sample_image):
        """Test prediction with custom top_k."""
        from src.utils import preprocess_image

        tensor = preprocess_image(sample_image)
        result = loaded_model.predict(tensor, top_k=10)

        assert len(result["predictions"]) == 10

    def test_predict_from_image(self, loaded_model, sample_image):
        """Test prediction directly from PIL image."""
        result = loaded_model.predict_from_image(sample_image, top_k=3)

        assert "predictions" in result
        assert "inference_time_ms" in result
        assert len(result["predictions"]) == 3

    def test_get_model_info(self, loaded_model):
        """Test getting model information."""
        info = loaded_model.get_model_info()

        assert "model_name" in info
        assert "device" in info
        assert "is_loaded" in info
        assert "num_classes" in info

        assert info["is_loaded"] is True
        assert info["num_classes"] == 1000

    def test_get_model_info_not_loaded(self, model_instance):
        """Test getting info when model is not loaded."""
        info = model_instance.get_model_info()

        assert info["is_loaded"] is False
        assert info["num_classes"] == 0

    def test_unload(self, loaded_model):
        """Test model unloading."""
        loaded_model.unload()

        assert loaded_model.is_loaded is False
        assert loaded_model.model is None
        assert len(loaded_model.labels) == 0

    def test_unload_not_loaded(self, model_instance):
        """Test unloading when model is not loaded."""
        # Should not raise exception, just log warning
        model_instance.unload()
        assert model_instance.is_loaded is False


class TestGlobalModelInstance:
    """Tests for global model instance management."""

    def test_initialize_model(self):
        """Test initializing global model instance."""
        # Clean up any existing instance
        cleanup_model()

        model = initialize_model(device="cpu")

        assert model is not None
        assert model.is_loaded is True

        # Clean up
        cleanup_model()

    def test_initialize_model_already_initialized(self):
        """Test initializing when already initialized."""
        cleanup_model()

        # Initialize twice
        model1 = initialize_model(device="cpu")
        model2 = initialize_model(device="cpu")

        # Should return same instance
        assert model1 is model2

        cleanup_model()

    def test_get_model_not_initialized(self):
        """Test getting model when not initialized."""
        cleanup_model()

        with pytest.raises(RuntimeError, match="Model not initialized"):
            get_model()

    def test_get_model_initialized(self):
        """Test getting initialized model."""
        cleanup_model()

        initialize_model(device="cpu")
        model = get_model()

        assert model is not None
        assert model.is_loaded is True

        cleanup_model()

    def test_cleanup_model(self):
        """Test cleaning up global model."""
        cleanup_model()

        # Initialize and then cleanup
        initialize_model(device="cpu")
        cleanup_model()

        # Should raise exception when trying to get model
        with pytest.raises(RuntimeError, match="Model not initialized"):
            get_model()

    def test_cleanup_model_not_initialized(self):
        """Test cleanup when not initialized."""
        cleanup_model()

        # Should not raise exception
        cleanup_model()


class TestModelInference:
    """Integration tests for model inference."""

    def test_inference_consistency(self, loaded_model, sample_image):
        """Test that inference is consistent for the same image."""
        result1 = loaded_model.predict_from_image(sample_image, top_k=5)
        result2 = loaded_model.predict_from_image(sample_image, top_k=5)

        # Same image should give same predictions
        preds1 = result1["predictions"]
        preds2 = result2["predictions"]

        assert len(preds1) == len(preds2)
        for p1, p2 in zip(preds1, preds2):
            assert p1["class_id"] == p2["class_id"]
            assert abs(p1["confidence"] - p2["confidence"]) < 1e-6

    def test_inference_probabilities_sum_to_one(self, loaded_model, sample_image):
        """Test that all class probabilities sum to ~1."""
        result = loaded_model.predict_from_image(sample_image, top_k=1000)

        total_prob = sum(p["confidence"] for p in result["predictions"])

        # Should be very close to 1.0
        assert abs(total_prob - 1.0) < 0.01

    def test_inference_sorted_by_confidence(self, loaded_model, sample_image):
        """Test that predictions are sorted by confidence."""
        result = loaded_model.predict_from_image(sample_image, top_k=10)

        predictions = result["predictions"]
        confidences = [p["confidence"] for p in predictions]

        # Should be in descending order
        assert confidences == sorted(confidences, reverse=True)
