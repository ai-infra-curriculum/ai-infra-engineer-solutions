"""X-Request-Id propagation."""
from __future__ import annotations

import contextvars
import uuid

from starlette.middleware.base import BaseHTTPMiddleware


REQUEST_ID: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = REQUEST_ID.set(rid)
        try:
            request.state.request_id = rid
            response = await call_next(request)
            response.headers["x-request-id"] = rid
            return response
        finally:
            REQUEST_ID.reset(token)
