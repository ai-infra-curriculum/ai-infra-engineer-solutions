"""
Configuration management for the model serving system.

Uses Pydantic for validation and environment variable loading.
"""

import os
from typing import Optional
from pydantic import BaseModel, Field, validator


class Settings(BaseModel):
    """Application settings loaded from environment variables."""

    # Application settings
    app_name: str = Field(default="model-serving-api", env="APP_NAME")
    app_version: str = Field(default="1.0.0", env="APP_VERSION")
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # API settings
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")
    api_workers: int = Field(default=1, env="API_WORKERS")
    max_upload_size: int = Field(default=10 * 1024 * 1024, env="MAX_UPLOAD_SIZE")  # 10MB

    # Model settings
    model_name: str = Field(default="resnet50", env="MODEL_NAME")
    model_device: str = Field(default="cpu", env="MODEL_DEVICE")
    model_cache_dir: Optional[str] = Field(default=None, env="MODEL_CACHE_DIR")
    top_k_predictions: int = Field(default=5, env="TOP_K_PREDICTIONS")

    # Performance settings
    batch_size: int = Field(default=1, env="BATCH_SIZE")
    inference_timeout: float = Field(default=30.0, env="INFERENCE_TIMEOUT")

    # Monitoring settings
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    metrics_port: int = Field(default=8000, env="METRICS_PORT")

    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level is one of the standard logging levels."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()

    @validator("model_device")
    def validate_device(cls, v):
        """Validate model device is either cpu or cuda."""
        if v.lower() not in ["cpu", "cuda"]:
            raise ValueError("Model device must be 'cpu' or 'cuda'")
        return v.lower()

    @validator("top_k_predictions")
    def validate_top_k(cls, v):
        """Validate top_k is between 1 and 1000."""
        if not 1 <= v <= 1000:
            raise ValueError("top_k_predictions must be between 1 and 1000")
        return v

    class Config:
        """Pydantic config."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


def get_settings() -> Settings:
    """
    Get application settings.

    Returns:
        Settings: Application settings loaded from environment variables
    """
    return Settings()


# Global settings instance
settings = get_settings()
