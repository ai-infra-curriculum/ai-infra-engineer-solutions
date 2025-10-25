"""
Utility functions for image processing and validation.
"""

import io
import logging
from typing import Optional, Tuple
from PIL import Image
import numpy as np
import torch
from torchvision import transforms
import requests
from requests.exceptions import RequestException, Timeout

from src.config import settings

logger = logging.getLogger(__name__)

# ImageNet normalization parameters
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

# Maximum image dimensions (to prevent memory issues)
MAX_IMAGE_WIDTH = 4096
MAX_IMAGE_HEIGHT = 4096


class ImageProcessingError(Exception):
    """Custom exception for image processing errors."""
    pass


class ImageDownloadError(Exception):
    """Custom exception for image download errors."""
    pass


def get_image_transform() -> transforms.Compose:
    """
    Get the standard ImageNet preprocessing transform.

    Returns:
        transforms.Compose: Composed transforms for preprocessing
    """
    return transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
    ])


def validate_image(image: Image.Image) -> None:
    """
    Validate image dimensions and format.

    Args:
        image: PIL Image to validate

    Raises:
        ImageProcessingError: If image is invalid
    """
    if image is None:
        raise ImageProcessingError("Image is None")

    width, height = image.size

    if width > MAX_IMAGE_WIDTH or height > MAX_IMAGE_HEIGHT:
        raise ImageProcessingError(
            f"Image dimensions {width}x{height} exceed maximum allowed "
            f"{MAX_IMAGE_WIDTH}x{MAX_IMAGE_HEIGHT}"
        )

    if width < 1 or height < 1:
        raise ImageProcessingError(
            f"Invalid image dimensions: {width}x{height}"
        )

    # Ensure image is in RGB mode
    if image.mode not in ["RGB", "RGBA", "L"]:
        raise ImageProcessingError(
            f"Unsupported image mode: {image.mode}. Expected RGB, RGBA, or L"
        )


def load_image_from_bytes(image_bytes: bytes) -> Image.Image:
    """
    Load and validate an image from bytes.

    Args:
        image_bytes: Raw image bytes

    Returns:
        Image.Image: PIL Image object in RGB mode

    Raises:
        ImageProcessingError: If image cannot be loaded or is invalid
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        validate_image(image)

        # Convert to RGB if necessary
        if image.mode != "RGB":
            image = image.convert("RGB")

        logger.debug(f"Loaded image: size={image.size}, mode={image.mode}")
        return image

    except Exception as e:
        if isinstance(e, ImageProcessingError):
            raise
        logger.error(f"Error loading image from bytes: {e}")
        raise ImageProcessingError(f"Failed to load image: {str(e)}")


def download_image_from_url(url: str, timeout: float = 10.0) -> bytes:
    """
    Download an image from a URL.

    Args:
        url: URL to download image from
        timeout: Request timeout in seconds

    Returns:
        bytes: Raw image bytes

    Raises:
        ImageDownloadError: If download fails
    """
    try:
        logger.debug(f"Downloading image from: {url}")

        # Validate URL format
        if not url.startswith(("http://", "https://")):
            raise ImageDownloadError(f"Invalid URL scheme: {url}")

        response = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "ModelServingAPI/1.0"},
            stream=True
        )
        response.raise_for_status()

        # Check content type
        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("image/"):
            raise ImageDownloadError(
                f"URL does not point to an image. Content-Type: {content_type}"
            )

        # Check content length
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > settings.max_upload_size:
            raise ImageDownloadError(
                f"Image size {content_length} bytes exceeds maximum "
                f"{settings.max_upload_size} bytes"
            )

        # Download with size limit
        image_bytes = b""
        for chunk in response.iter_content(chunk_size=8192):
            image_bytes += chunk
            if len(image_bytes) > settings.max_upload_size:
                raise ImageDownloadError(
                    f"Image size exceeds maximum {settings.max_upload_size} bytes"
                )

        logger.debug(f"Downloaded {len(image_bytes)} bytes from {url}")
        return image_bytes

    except Timeout:
        raise ImageDownloadError(f"Timeout downloading image from {url}")
    except RequestException as e:
        raise ImageDownloadError(f"Failed to download image: {str(e)}")
    except Exception as e:
        if isinstance(e, ImageDownloadError):
            raise
        raise ImageDownloadError(f"Unexpected error downloading image: {str(e)}")


def preprocess_image(image: Image.Image) -> torch.Tensor:
    """
    Preprocess image for model inference.

    Args:
        image: PIL Image in RGB mode

    Returns:
        torch.Tensor: Preprocessed image tensor (1, 3, 224, 224)

    Raises:
        ImageProcessingError: If preprocessing fails
    """
    try:
        transform = get_image_transform()
        tensor = transform(image)

        # Add batch dimension
        tensor = tensor.unsqueeze(0)

        logger.debug(f"Preprocessed image tensor shape: {tensor.shape}")
        return tensor

    except Exception as e:
        logger.error(f"Error preprocessing image: {e}")
        raise ImageProcessingError(f"Failed to preprocess image: {str(e)}")


def load_imagenet_labels() -> list:
    """
    Load ImageNet class labels.

    Returns:
        list: List of 1000 ImageNet class labels

    Raises:
        RuntimeError: If labels cannot be loaded
    """
    try:
        # ImageNet labels URL
        labels_url = (
            "https://raw.githubusercontent.com/pytorch/hub/master/"
            "imagenet_classes.txt"
        )

        response = requests.get(labels_url, timeout=10)
        response.raise_for_status()

        labels = response.text.strip().split("\n")

        if len(labels) != 1000:
            raise RuntimeError(
                f"Expected 1000 labels, got {len(labels)}"
            )

        logger.info("Successfully loaded ImageNet labels")
        return labels

    except Exception as e:
        logger.error(f"Error loading ImageNet labels: {e}")
        # Fallback: return generic labels
        logger.warning("Using generic labels as fallback")
        return [f"class_{i}" for i in range(1000)]


def format_predictions(
    probabilities: torch.Tensor,
    labels: list,
    top_k: int = 5
) -> list:
    """
    Format model predictions into a readable structure.

    Args:
        probabilities: Tensor of class probabilities (1, 1000)
        labels: List of class labels
        top_k: Number of top predictions to return

    Returns:
        list: List of dicts with 'class', 'label', and 'confidence' keys
    """
    # Get top k predictions
    top_probs, top_indices = torch.topk(probabilities, top_k)

    predictions = []
    for prob, idx in zip(top_probs[0], top_indices[0]):
        predictions.append({
            "class_id": int(idx),
            "label": labels[idx],
            "confidence": float(prob)
        })

    return predictions


def tensor_to_device(tensor: torch.Tensor, device: str) -> torch.Tensor:
    """
    Move tensor to specified device.

    Args:
        tensor: Input tensor
        device: Target device ('cpu' or 'cuda')

    Returns:
        torch.Tensor: Tensor on target device
    """
    try:
        return tensor.to(device)
    except Exception as e:
        logger.warning(f"Failed to move tensor to {device}: {e}. Using CPU.")
        return tensor.to("cpu")
