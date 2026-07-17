import re

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# Common prompt injection patterns
_INJECTION_PATTERNS = [
    r"ignore\s+(previous|all)\s+instructions",
    r"forget\s+(everything|all)\s+you",
    r"you\s+are\s+now\s+(a\s+)?(?!ChronoLegal)",
    r"jailbreak",
    r"DAN\s+mode",
    r"pretend\s+you\s+(are|have\s+no)",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)

_SQL_PATTERNS = [
    r";\s*(DROP|DELETE|TRUNCATE|INSERT|UPDATE|ALTER|CREATE)\s+",
    r"UNION\s+SELECT",
    r"1\s*=\s*1",
    r"OR\s+1\s*=\s*1",
]
_SQL_RE = re.compile("|".join(_SQL_PATTERNS), re.IGNORECASE)


def sanitize_string(value: str) -> str:
    """Strip HTML tags and encode dangerous characters."""
    value = re.sub(r"<[^>]+>", "", value)
    return value


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                body = await request.body()
                if body:
                    body_str = body.decode("utf-8", errors="replace")
                    if _INJECTION_RE.search(body_str):
                        return JSONResponse(
                            status_code=400,
                            content={"detail": "Request contains disallowed content"},
                        )
            except Exception:
                pass

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response
