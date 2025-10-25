"""
Tests for FastAPI application.
"""

import io
import json
import pytest
from unittest.mock import patch, Mock
from PIL import Image

from src.api import app


class TestRootEndpoint:
    """Tests for root endpoint."""

    def test_root(self, test_client):
        """Test root endpoint returns API information."""
        response = test_client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check_healthy(self, test_client):
        """Test health check when service is healthy."""
        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["model_loaded"] is True
        assert "timestamp" in data
        assert "version" in data

    @patch("src.api.get_model")
    def test_health_check_unhealthy(self, mock_get_model, test_client):
        """Test health check when model is not loaded."""
        mock_model = Mock()
        mock_model.is_loaded = False
        mock_get_model.return_value = mock_model

        response = test_client.get("/health")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["model_loaded"] is False

    @patch("src.api.get_model")
    def test_health_check_exception(self, mock_get_model, test_client):
        """Test health check when exception occurs."""
        mock_get_model.side_effect = Exception("Model error")

        response = test_client.get("/health")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"


class TestReadinessEndpoint:
    """Tests for readiness check endpoint."""

    def test_readiness_ready(self, test_client):
        """Test readiness check when service is ready."""
        response = test_client.get("/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

    @patch("src.api.get_model")
    def test_readiness_not_ready(self, mock_get_model, test_client):
        """Test readiness check when service is not ready."""
        mock_model = Mock()
        mock_model.is_loaded = False
        mock_get_model.return_value = mock_model

        response = test_client.get("/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not ready"


class TestModelInfoEndpoint:
    """Tests for model info endpoint."""

    def test_model_info(self, test_client):
        """Test getting model information."""
        response = test_client.get("/model/info")

        assert response.status_code == 200
        data = response.json()
        assert "model_name" in data
        assert "device" in data
        assert "is_loaded" in data

    @patch("src.api.get_model")
    def test_model_info_error(self, mock_get_model, test_client):
        """Test model info endpoint when error occurs."""
        mock_get_model.side_effect = Exception("Model error")

        response = test_client.get("/model/info")

        assert response.status_code == 500


class TestPredictFromFileEndpoint:
    """Tests for file upload prediction endpoint."""

    def test_predict_from_file_success(self, test_client, sample_image_bytes):
        """Test successful prediction from file upload."""
        files = {"file": ("test.jpg", io.BytesIO(sample_image_bytes), "image/jpeg")}

        response = test_client.post("/predict", files=files)

        assert response.status_code == 200
        data = response.json()
        assert "predictions" in data
        assert "inference_time_ms" in data
        assert len(data["predictions"]) == 5  # Default top_k

        # Check prediction structure
        pred = data["predictions"][0]
        assert "class_id" in pred
        assert "label" in pred
        assert "confidence" in pred

    def test_predict_from_file_with_top_k(self, test_client, sample_image_bytes):
        """Test prediction with custom top_k parameter."""
        files = {"file": ("test.jpg", io.BytesIO(sample_image_bytes), "image/jpeg")}
        params = {"top_k": 10}

        response = test_client.post("/predict", files=files, params=params)

        assert response.status_code == 200
        data = response.json()
        assert len(data["predictions"]) == 10

    def test_predict_from_file_invalid_content_type(self, test_client):
        """Test prediction with invalid content type."""
        files = {"file": ("test.txt", io.BytesIO(b"not an image"), "text/plain")}

        response = test_client.post("/predict", files=files)

        assert response.status_code == 400
        assert "Invalid content type" in response.json()["detail"]

    def test_predict_from_file_invalid_image(self, test_client):
        """Test prediction with invalid image data."""
        files = {"file": ("test.jpg", io.BytesIO(b"invalid image data"), "image/jpeg")}

        response = test_client.post("/predict", files=files)

        assert response.status_code == 400
        assert "Image processing failed" in response.json()["detail"]

    def test_predict_from_file_too_large(self, test_client):
        """Test prediction with file size exceeding limit."""
        # Create a large fake image (>10MB)
        large_data = b"x" * (11 * 1024 * 1024)
        files = {"file": ("large.jpg", io.BytesIO(large_data), "image/jpeg")}

        response = test_client.post("/predict", files=files)

        assert response.status_code == 413
        assert "exceeds maximum" in response.json()["detail"]

    def test_predict_from_file_invalid_top_k(self, test_client, sample_image_bytes):
        """Test prediction with invalid top_k parameter."""
        files = {"file": ("test.jpg", io.BytesIO(sample_image_bytes), "image/jpeg")}
        params = {"top_k": 1000}  # Too large

        response = test_client.post("/predict", files=files, params=params)

        # Should return 422 for validation error
        assert response.status_code == 422


class TestPredictFromURLEndpoint:
    """Tests for URL-based prediction endpoint."""

    @patch("src.api.download_image_from_url")
    @patch("src.api.load_image_from_bytes")
    def test_predict_from_url_success(
        self,
        mock_load_image,
        mock_download,
        test_client,
        sample_image,
        sample_image_bytes
    ):
        """Test successful prediction from URL."""
        mock_download.return_value = sample_image_bytes
        mock_load_image.return_value = sample_image

        payload = {"url": "https://example.com/image.jpg", "top_k": 5}

        response = test_client.post("/predict/url", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "predictions" in data
        assert "inference_time_ms" in data
        assert len(data["predictions"]) == 5

    @patch("src.api.download_image_from_url")
    def test_predict_from_url_download_error(self, mock_download, test_client):
        """Test prediction when image download fails."""
        from src.utils import ImageDownloadError

        mock_download.side_effect = ImageDownloadError("Download failed")

        payload = {"url": "https://example.com/image.jpg"}

        response = test_client.post("/predict/url", json=payload)

        assert response.status_code == 400
        assert "Failed to download image" in response.json()["detail"]

    @patch("src.api.download_image_from_url")
    @patch("src.api.load_image_from_bytes")
    def test_predict_from_url_processing_error(
        self,
        mock_load_image,
        mock_download,
        test_client,
        sample_image_bytes
    ):
        """Test prediction when image processing fails."""
        from src.utils import ImageProcessingError

        mock_download.return_value = sample_image_bytes
        mock_load_image.side_effect = ImageProcessingError("Invalid image")

        payload = {"url": "https://example.com/image.jpg"}

        response = test_client.post("/predict/url", json=payload)

        assert response.status_code == 400
        assert "Image processing failed" in response.json()["detail"]

    def test_predict_from_url_invalid_url(self, test_client):
        """Test prediction with invalid URL."""
        payload = {"url": "not-a-valid-url"}

        response = test_client.post("/predict/url", json=payload)

        # Should return 422 for validation error
        assert response.status_code == 422

    def test_predict_from_url_invalid_top_k(self, test_client):
        """Test prediction with invalid top_k."""
        payload = {"url": "https://example.com/image.jpg", "top_k": 1000}

        response = test_client.post("/predict/url", json=payload)

        # Should return 422 for validation error
        assert response.status_code == 422


class TestAPIDocumentation:
    """Tests for API documentation."""

    def test_openapi_schema(self, test_client):
        """Test that OpenAPI schema is available."""
        response = test_client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema

    def test_docs_endpoint(self, test_client):
        """Test that Swagger UI docs are available."""
        response = test_client.get("/docs")

        assert response.status_code == 200


class TestErrorHandling:
    """Tests for error handling."""

    @patch("src.api.get_model")
    def test_internal_server_error(self, mock_get_model, test_client):
        """Test internal server error handling."""
        # Simulate an unexpected error
        mock_get_model.side_effect = RuntimeError("Unexpected error")

        response = test_client.get("/model/info")

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data


class TestMetricsEndpoint:
    """Tests for Prometheus metrics endpoint."""

    def test_metrics_endpoint_exists(self, test_client):
        """Test that metrics endpoint exists."""
        # Metrics are disabled in test environment
        # but endpoint should still exist
        response = test_client.get("/metrics")

        # Should either return metrics or 404 depending on config
        assert response.status_code in [200, 404]


class TestIntegrationFlow:
    """Integration tests for complete workflows."""

    def test_complete_prediction_flow(self, test_client, sample_image):
        """Test complete prediction flow from image to response."""
        # Convert image to bytes
        buffer = io.BytesIO()
        sample_image.save(buffer, format="JPEG")
        buffer.seek(0)

        files = {"file": ("test.jpg", buffer, "image/jpeg")}

        # Make prediction
        response = test_client.post("/predict", files=files, params={"top_k": 3})

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert "predictions" in data
        assert "inference_time_ms" in data
        assert "preprocessing_time_ms" in data

        predictions = data["predictions"]
        assert len(predictions) == 3

        # Validate predictions are sorted by confidence
        confidences = [p["confidence"] for p in predictions]
        assert confidences == sorted(confidences, reverse=True)

        # Validate confidence is between 0 and 1
        for pred in predictions:
            assert 0 <= pred["confidence"] <= 1

    def test_health_to_prediction_flow(self, test_client, sample_image_bytes):
        """Test health check followed by prediction."""
        # First check health
        health_response = test_client.get("/health")
        assert health_response.status_code == 200
        assert health_response.json()["status"] == "healthy"

        # Then make prediction
        files = {"file": ("test.jpg", io.BytesIO(sample_image_bytes), "image/jpeg")}
        predict_response = test_client.post("/predict", files=files)

        assert predict_response.status_code == 200
