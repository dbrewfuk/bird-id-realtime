from __future__ import annotations

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

from app.config import settings

COOKIE_NAME = "bird_id_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days

# Paths that never require authentication
PUBLIC_PATHS = {"/login", "/logout", "/api/health"}


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt="bird-id-login")


def make_session_cookie() -> str:
    return _serializer().dumps("authenticated")


def verify_session_cookie(token: str) -> bool:
    try:
        _serializer().loads(token, max_age=COOKIE_MAX_AGE)
        return True
    except (BadSignature, SignatureExpired, Exception):
        return False


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Static files and public paths are always allowed
        if path.startswith("/static/") or path in PUBLIC_PATHS:
            return await call_next(request)

        token = request.cookies.get(COOKIE_NAME)
        if token and verify_session_cookie(token):
            return await call_next(request)

        # API routes → 401 JSON so JS can surface a message
        if path.startswith("/api/"):
            return JSONResponse({"detail": "Unauthenticated"}, status_code=401)

        # All other routes → redirect to login
        return RedirectResponse(url="/login", status_code=302)
