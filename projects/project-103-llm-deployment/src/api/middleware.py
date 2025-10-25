"""
Middleware for FastAPI application

Includes:
- Request logging
- Error handling
- Rate limiting
- Request ID tracking
"""

import logging
import time
import uuid
from typing import Callable

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests and responses"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Log request
        logger.info(
            f"Request {request_id}: {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}"
        )

        # Time the request
        start_time = time.time()

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Log response
            logger.info(
                f"Response {request_id}: {response.status_code} "
                f"in {duration:.3f}s"
            )

            # Add headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{duration:.3f}"

            return response

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Request {request_id} failed after {duration:.3f}s: {e}",
                exc_info=True,
            )
            raise


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Handle errors gracefully"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)

        except Exception as e:
            # Log error
            logger.error(f"Unhandled error: {e}", exc_info=True)

            # Return error response
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Internal server error",
                    "detail": str(e),
                    "request_id": getattr(request.state, "request_id", None),
                },
            )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware"""

    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests = {}  # IP -> list of timestamps

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"

        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/ready", "/metrics"]:
            return await call_next(request)

        # Clean old timestamps
        current_time = time.time()
        if client_ip in self.requests:
            self.requests[client_ip] = [
                t for t in self.requests[client_ip] if current_time - t < 60
            ]

        # Check rate limit
        if client_ip in self.requests:
            if len(self.requests[client_ip]) >= self.requests_per_minute:
                logger.warning(f"Rate limit exceeded for {client_ip}")
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "Rate limit exceeded",
                        "detail": f"Maximum {self.requests_per_minute} requests per minute",
                    },
                )

        # Record request
        if client_ip not in self.requests:
            self.requests[client_ip] = []
        self.requests[client_ip].append(current_time)

        return await call_next(request)


def add_middlewares(app: FastAPI):
    """Add all middlewares to the app"""

    # Gzip compression
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Custom middlewares
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(ErrorHandlingMiddleware)

    # Rate limiting (configurable via env)
    import os

    requests_per_minute = int(os.getenv("RATE_LIMIT_RPM", "60"))
    app.add_middleware(RateLimitMiddleware, requests_per_minute=requests_per_minute)

    logger.info("Middlewares added successfully")
