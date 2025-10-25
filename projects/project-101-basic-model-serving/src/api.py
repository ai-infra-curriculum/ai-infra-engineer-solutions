"""
FastAPI application for model serving.

This module provides REST API endpoints for image classification using ResNet50.
"""

import logging
import time
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl, validator
from prometheus_fastapi_instrumentator import Instrumentator
import uvicorn

from src.config import settings
from src.model import initialize_model, cleanup_model, get_model
from src.utils import (
    load_image_from_bytes,
    download_image_from_url,
    ImageProcessingError,
    ImageDownloadError
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Pydantic models for request/response
class PredictURLRequest(BaseModel):
    """Request model for URL-based prediction."""
    url: HttpUrl
    top_k: Optional[int] = None

    @validator("top_k")
    def validate_top_k(cls, v):
        if v is not None and not 1 <= v <= 100:
            raise ValueError("top_k must be between 1 and 100")
        return v


class PredictionResponse(BaseModel):
    """Response model for predictions."""
    predictions: list
    inference_time_ms: float
    preprocessing_time_ms: Optional[float] = None


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    model_loaded: bool
    timestamp: float
    version: str


class ErrorResponse(BaseModel):
    """Response model for errors."""
    error: str
    detail: Optional[str] = None


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI application.

    Handles model initialization on startup and cleanup on shutdown.
    """
    # Startup
    logger.info("Starting up application...")
    try:
        initialize_model()
        logger.info("Application startup complete")
    except Exception as e:
        logger.error(f"Failed to initialize model: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down application...")
    cleanup_model()
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Production-ready ML model serving API for image classification",
    lifespan=lifespan
)

# Add Prometheus instrumentation
if settings.enable_metrics:
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=[".*admin.*", "/metrics"],
        env_var_name="ENABLE_METRICS",
        inprogress_name="http_requests_inprogress",
        inprogress_labels=True,
    )
    instrumentator.instrument(app)
    instrumentator.expose(app, include_in_schema=False, endpoint="/metrics")
    logger.info("Prometheus metrics enabled at /metrics")


# Root endpoint
@app.get("/", tags=["general"])
async def root() -> Dict[str, str]:
    """
    Root endpoint with API information.

    Returns:
        dict: Basic API information
    """
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "Image classification API using ResNet50",
        "docs": "/docs",
        "health": "/health"
    }


# Health check endpoint
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["monitoring"],
    summary="Health check endpoint"
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint for Kubernetes probes.

    Returns:
        HealthResponse: Health status information

    Status Codes:
        200: Service is healthy
        503: Service is unhealthy (model not loaded)
    """
    try:
        model = get_model()
        model_loaded = model.is_loaded
        status_str = "healthy" if model_loaded else "unhealthy"

        response = HealthResponse(
            status=status_str,
            model_loaded=model_loaded,
            timestamp=time.time(),
            version=settings.app_version
        )

        # Return 503 if model is not loaded
        if not model_loaded:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=response.dict()
            )

        return response

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "model_loaded": False,
                "timestamp": time.time(),
                "version": settings.app_version,
                "error": str(e)
            }
        )


# Readiness check endpoint
@app.get(
    "/ready",
    tags=["monitoring"],
    summary="Readiness check endpoint"
)
async def readiness_check() -> Dict[str, Any]:
    """
    Readiness check endpoint for Kubernetes.

    Returns:
        dict: Readiness status

    Status Codes:
        200: Service is ready
        503: Service is not ready
    """
    try:
        model = get_model()
        if model.is_loaded:
            return {"status": "ready", "timestamp": time.time()}
        else:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "not ready", "timestamp": time.time()}
            )
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not ready",
                "timestamp": time.time(),
                "error": str(e)
            }
        )


# Model info endpoint
@app.get(
    "/model/info",
    tags=["model"],
    summary="Get model information"
)
async def model_info() -> Dict[str, Any]:
    """
    Get information about the loaded model.

    Returns:
        dict: Model information
    """
    try:
        model = get_model()
        return model.get_model_info()
    except Exception as e:
        logger.error(f"Failed to get model info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get model info: {str(e)}"
        )


# Prediction endpoint - File upload
@app.post(
    "/predict",
    response_model=PredictionResponse,
    tags=["prediction"],
    summary="Predict from uploaded image file"
)
async def predict_from_file(
    file: UploadFile = File(..., description="Image file to classify"),
    top_k: Optional[int] = Query(
        None,
        ge=1,
        le=100,
        description="Number of top predictions to return"
    )
) -> PredictionResponse:
    """
    Perform image classification on an uploaded file.

    Args:
        file: Image file (JPEG, PNG, etc.)
        top_k: Number of top predictions to return (default: 5)

    Returns:
        PredictionResponse: Predictions with confidence scores

    Raises:
        HTTPException: If prediction fails

    Example:
        ```bash
        curl -X POST "http://localhost:8000/predict" \\
             -F "file=@image.jpg" \\
             -F "top_k=5"
        ```
    """
    preprocessing_start = time.time()

    try:
        # Validate content type
        if not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid content type: {file.content_type}. Expected image/*"
            )

        # Read file contents
        contents = await file.read()

        # Validate file size
        if len(contents) > settings.max_upload_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size {len(contents)} exceeds maximum "
                       f"{settings.max_upload_size} bytes"
            )

        # Load and validate image
        image = load_image_from_bytes(contents)

        preprocessing_time = (time.time() - preprocessing_start) * 1000

        # Get model and predict
        model = get_model()
        result = model.predict_from_image(image, top_k=top_k)

        # Add preprocessing time
        result["preprocessing_time_ms"] = preprocessing_time

        return PredictionResponse(**result)

    except ImageProcessingError as e:
        logger.warning(f"Image processing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image processing failed: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction failed: {str(e)}"
        )


# Prediction endpoint - URL
@app.post(
    "/predict/url",
    response_model=PredictionResponse,
    tags=["prediction"],
    summary="Predict from image URL"
)
async def predict_from_url(
    request: PredictURLRequest
) -> PredictionResponse:
    """
    Perform image classification on an image from URL.

    Args:
        request: Request containing image URL and optional top_k

    Returns:
        PredictionResponse: Predictions with confidence scores

    Raises:
        HTTPException: If prediction fails

    Example:
        ```bash
        curl -X POST "http://localhost:8000/predict/url" \\
             -H "Content-Type: application/json" \\
             -d '{"url": "https://example.com/image.jpg", "top_k": 5}'
        ```
    """
    preprocessing_start = time.time()

    try:
        # Download image
        image_bytes = download_image_from_url(str(request.url))

        # Load and validate image
        image = load_image_from_bytes(image_bytes)

        preprocessing_time = (time.time() - preprocessing_start) * 1000

        # Get model and predict
        model = get_model()
        result = model.predict_from_image(image, top_k=request.top_k)

        # Add preprocessing time
        result["preprocessing_time_ms"] = preprocessing_time

        return PredictionResponse(**result)

    except ImageDownloadError as e:
        logger.warning(f"Image download error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to download image: {str(e)}"
        )
    except ImageProcessingError as e:
        logger.warning(f"Image processing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image processing failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction failed: {str(e)}"
        )


# Custom exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc) if settings.debug else None
        ).dict()
    )


def main():
    """Run the application with uvicorn."""
    uvicorn.run(
        "src.api:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        log_level=settings.log_level.lower(),
        reload=settings.debug
    )


if __name__ == "__main__":
    main()
