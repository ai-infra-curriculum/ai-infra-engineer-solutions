"""Admin endpoints: gated by X-Admin-Token."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request

from ..ml import loader


router = APIRouter(prefix="/v1/admin")


def _check_token(request: Request, token: str | None) -> None:
    expected = request.app.state.settings.admin_token
    if not token or token != expected:
        raise HTTPException(401, "admin token required")


@router.post("/reload")
def reload(request: Request, x_admin_token: str = Header(default=None)) -> dict:
    _check_token(request, x_admin_token)
    loader.reload()
    return {"reloaded": True, "version": loader.get_version()}
