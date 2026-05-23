"""FastAPI factory + lifespan management."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from .config import Settings
from .instrumentation import MODEL_INFO
from .logging_config import configure as configure_logging
from .middleware.body_size import BodySizeLimitMiddleware
from .middleware.rate_limit import build_limiter
from .middleware.request_id import RequestIDMiddleware
from .ml import loader
from .routes import admin, health, predict


log = logging.getLogger("model_serve.app")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await asyncio.to_thread(loader.load, settings.model_path, settings.model_version)
        MODEL_INFO.labels(version=settings.model_version).set(1)
        log.info("startup complete; model %s loaded", settings.model_version)
        yield
        log.info("shutdown")

    app = FastAPI(title="model-serve", lifespan=lifespan)
    app.state.settings = settings

    # Middleware (order matters: outer-to-inner)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)

    limiter = build_limiter(settings.rate_limit_per_min)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Routes
    app.include_router(health.router)
    app.include_router(predict.router)
    app.include_router(admin.router)

    # Prometheus /metrics
    Instrumentator().instrument(app).expose(app)

    return app


# For uvicorn / gunicorn entrypoint
app = create_app()
