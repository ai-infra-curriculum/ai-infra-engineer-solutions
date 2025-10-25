"""
Tests for utility functions.
"""

import io
import pytest
import torch
from PIL import Image
from unittest.mock import patch, Mock
import requests

from src.utils import (
    get_image_transform,
    validate_image,
    load_image_from_bytes,
    download_image_from_url,
    preprocess_image,
    load_imagenet_labels,
    format_predictions,
    tensor_to_device,
    ImageProcessingError,
    ImageDownloadError,
)


class TestImageTransform:
    """Tests for image transformation."""

    def test_get_image_transform(self):
        """Test that image transform is created correctly."""
        transform = get_image_transform()
        assert transform is not None

    def test_transform_output_shape(self, sample_image):
        """Test that transform produces correct output shape."""
        transform = get_image_transform()
        tensor = transform(sample_image)

        # Should be (3, 224, 224)
        assert tensor.shape == (3, 224, 224)
        assert tensor.dtype == torch.float32


class TestValidateImage:
    """Tests for image validation."""

    def test_validate_valid_image(self, sample_image):
        """Test validation of a valid image."""
        # Should not raise exception
        validate_image(sample_image)

    def test_validate_none_image(self):
        """Test validation of None image."""
        with pytest.raises(ImageProcessingError, match="Image is None"):
            validate_image(None)

    def test_validate_oversized_image(self):
        """Test validation of oversized image."""
        huge_image = Image.new("RGB", (5000, 5000))
        with pytest.raises(ImageProcessingError, match="exceed maximum"):
            validate_image(huge_image)

    def test_validate_zero_dimension_image(self):
        """Test validation of image with zero dimensions."""
        # PIL doesn't allow creation of zero-size images, so we mock
        mock_image = Mock()
        mock_image.size = (0, 100)

        with pytest.raises(ImageProcessingError, match="Invalid image dimensions"):
            validate_image(mock_image)

    def test_validate_grayscale_image(self, sample_grayscale_image):
        """Test validation of grayscale image."""
        # Should not raise exception
        validate_image(sample_grayscale_image)


class TestLoadImageFromBytes:
    """Tests for loading images from bytes."""

    def test_load_valid_image(self, sample_image_bytes):
        """Test loading a valid image from bytes."""
        image = load_image_from_bytes(sample_image_bytes)

        assert isinstance(image, Image.Image)
        assert image.mode == "RGB"

    def test_load_invalid_bytes(self):
        """Test loading invalid image bytes."""
        invalid_bytes = b"not an image"

        with pytest.raises(ImageProcessingError, match="Failed to load image"):
            load_image_from_bytes(invalid_bytes)

    def test_load_empty_bytes(self):
        """Test loading empty bytes."""
        with pytest.raises(ImageProcessingError):
            load_image_from_bytes(b"")

    def test_load_grayscale_converts_to_rgb(self, sample_grayscale_image):
        """Test that grayscale images are converted to RGB."""
        # Convert grayscale image to bytes
        buffer = io.BytesIO()
        sample_grayscale_image.save(buffer, format="PNG")
        buffer.seek(0)
        image_bytes = buffer.getvalue()

        # Load and check mode
        image = load_image_from_bytes(image_bytes)
        assert image.mode == "RGB"


class TestDownloadImageFromURL:
    """Tests for downloading images from URLs."""

    @patch("src.utils.requests.get")
    def test_download_success(self, mock_get, sample_image_bytes):
        """Test successful image download."""
        # Mock successful response
        mock_response = Mock()
        mock_response.headers = {"content-type": "image/jpeg"}
        mock_response.iter_content = Mock(return_value=[sample_image_bytes])
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = download_image_from_url("https://example.com/image.jpg")

        assert result == sample_image_bytes
        mock_get.assert_called_once()

    @patch("src.utils.requests.get")
    def test_download_invalid_scheme(self, mock_get):
        """Test download with invalid URL scheme."""
        with pytest.raises(ImageDownloadError, match="Invalid URL scheme"):
            download_image_from_url("ftp://example.com/image.jpg")

    @patch("src.utils.requests.get")
    def test_download_wrong_content_type(self, mock_get):
        """Test download with wrong content type."""
        mock_response = Mock()
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with pytest.raises(ImageDownloadError, match="does not point to an image"):
            download_image_from_url("https://example.com/page.html")

    @patch("src.utils.requests.get")
    def test_download_timeout(self, mock_get):
        """Test download timeout."""
        mock_get.side_effect = requests.Timeout()

        with pytest.raises(ImageDownloadError, match="Timeout"):
            download_image_from_url("https://example.com/image.jpg")

    @patch("src.utils.requests.get")
    def test_download_request_exception(self, mock_get):
        """Test download with request exception."""
        mock_get.side_effect = requests.RequestException("Network error")

        with pytest.raises(ImageDownloadError, match="Failed to download"):
            download_image_from_url("https://example.com/image.jpg")

    @patch("src.utils.requests.get")
    def test_download_size_limit(self, mock_get):
        """Test download with size exceeding limit."""
        # Mock response with large content
        large_data = b"x" * (11 * 1024 * 1024)  # 11MB
        mock_response = Mock()
        mock_response.headers = {
            "content-type": "image/jpeg",
            "content-length": str(len(large_data))
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with pytest.raises(ImageDownloadError, match="exceeds maximum"):
            download_image_from_url("https://example.com/large.jpg")


class TestPreprocessImage:
    """Tests for image preprocessing."""

    def test_preprocess_valid_image(self, sample_image):
        """Test preprocessing a valid image."""
        tensor = preprocess_image(sample_image)

        # Should be (1, 3, 224, 224) - batch dimension added
        assert tensor.shape == (1, 3, 224, 224)
        assert tensor.dtype == torch.float32

    def test_preprocess_large_image(self, large_image):
        """Test preprocessing a large image (should be resized)."""
        tensor = preprocess_image(large_image)

        # Should still be (1, 3, 224, 224) after preprocessing
        assert tensor.shape == (1, 3, 224, 224)


class TestLoadImageNetLabels:
    """Tests for loading ImageNet labels."""

    @patch("src.utils.requests.get")
    def test_load_labels_success(self, mock_get):
        """Test successful label loading."""
        # Mock response with 1000 labels
        labels_text = "\n".join([f"class_{i}" for i in range(1000)])
        mock_response = Mock()
        mock_response.text = labels_text
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        labels = load_imagenet_labels()

        assert len(labels) == 1000
        assert labels[0] == "class_0"

    @patch("src.utils.requests.get")
    def test_load_labels_failure_fallback(self, mock_get):
        """Test label loading failure returns fallback labels."""
        mock_get.side_effect = Exception("Network error")

        labels = load_imagenet_labels()

        # Should return fallback generic labels
        assert len(labels) == 1000
        assert all(label.startswith("class_") for label in labels)


class TestFormatPredictions:
    """Tests for formatting predictions."""

    def test_format_predictions(self):
        """Test formatting of predictions."""
        # Create mock probabilities
        probabilities = torch.tensor([[0.5, 0.3, 0.15, 0.04, 0.01]])
        labels = ["dog", "cat", "bird", "fish", "lizard"]

        predictions = format_predictions(probabilities, labels, top_k=3)

        assert len(predictions) == 3
        assert predictions[0]["label"] == "dog"
        assert predictions[0]["confidence"] == pytest.approx(0.5)
        assert predictions[0]["class_id"] == 0

        # Check descending order
        assert predictions[0]["confidence"] >= predictions[1]["confidence"]
        assert predictions[1]["confidence"] >= predictions[2]["confidence"]

    def test_format_predictions_top_k(self):
        """Test formatting with different top_k values."""
        probabilities = torch.randn(1, 100).softmax(dim=1)
        labels = [f"class_{i}" for i in range(100)]

        predictions = format_predictions(probabilities, labels, top_k=10)

        assert len(predictions) == 10


class TestTensorToDevice:
    """Tests for tensor device movement."""

    def test_tensor_to_cpu(self):
        """Test moving tensor to CPU."""
        tensor = torch.randn(1, 3, 224, 224)
        result = tensor_to_device(tensor, "cpu")

        assert result.device.type == "cpu"

    def test_tensor_to_invalid_device_fallback(self):
        """Test moving tensor to invalid device falls back to CPU."""
        tensor = torch.randn(1, 3, 224, 224)

        # Try to move to invalid device
        result = tensor_to_device(tensor, "invalid")

        # Should fall back to CPU
        assert result.device.type == "cpu"
