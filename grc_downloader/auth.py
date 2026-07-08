from __future__ import annotations

import secrets
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp


PUBLIC_PATHS = frozenset({
    "/health",
    "/api/health",
    "/metrics",
})


def _path_is_public(path: str) -> bool:
    if path in PUBLIC_PATHS:
        return True
    if path.startswith("/static/"):
        return True
    return False


def check_api_key(request: Request, expected: str | None) -> bool:
    if not expected:
        return True
    provided = request.headers.get("X-SN-API-Key", "")
    return secrets.compare_digest(provided, expected)


def check_basic_auth(request: Request, user: str | None, password: str | None) -> bool:
    if not user or not password:
        return True
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Basic "):
        return False
    import base64

    try:
        decoded = base64.b64decode(auth[6:]).decode("utf-8")
    except Exception:
        return False
    if ":" not in decoded:
        return False
    u, p = decoded.split(":", 1)
    return secrets.compare_digest(u, user) and secrets.compare_digest(p, password)


class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        *,
        auth_user: str | None = None,
        auth_password: str | None = None,
        api_key: str | None = None,
        dev_mode: bool = True,
    ):
        super().__init__(app)
        self.auth_user = auth_user
        self.auth_password = auth_password
        self.api_key = api_key
        self.dev_mode = dev_mode

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if self.dev_mode or _path_is_public(path):
            return await call_next(request)

        basic_ok = check_basic_auth(request, self.auth_user, self.auth_password)
        api_ok = check_api_key(request, self.api_key)

        if self.auth_user and not basic_ok:
            return Response(
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Security Now"'},
                content="Unauthorized",
            )

        if request.method in ("POST", "PUT", "DELETE", "PATCH") and path.startswith("/api/"):
            if self.api_key and not api_ok and not basic_ok:
                return JSONResponse(status_code=403, content={"error": "Invalid or missing API key"})

        return await call_next(request)