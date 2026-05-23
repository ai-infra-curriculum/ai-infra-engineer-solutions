"""Environment-driven settings."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MODEL_SERVE_")

    model_path: str = "/models/current/model.joblib"
    model_version: str = "v1"
    feature_count: int = 10
    max_batch: int = 128
    log_level: str = "INFO"
    rate_limit_per_min: int = 60
    max_body_bytes: int = 1_048_576    # 1 MB
    admin_token: str = "change-me"
