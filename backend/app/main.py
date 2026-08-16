import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.router import api_router
from app.api.websocket import router as ws_router
from app.core.config import settings
from app.core.database import run_migrations
from app.core.exceptions import AppException
from app.core.logging import setup_logging
from app.core.redis import close_redis, get_redis
from app.middleware.rate_limit import limiter
from app.middleware.security import SecurityMiddleware


async def _warmup_models() -> None:
    """Load embedding model and reranker eagerly so the first request pays no model-load penalty."""
    loop = asyncio.get_event_loop()
    try:
        from app.services.ai.embedding_service import _get_embedding_model

        await loop.run_in_executor(None, _get_embedding_model)
        logger.info("Embedding model warmed up")
    except Exception as exc:
        logger.warning(f"Embedding model warmup failed (non-fatal): {exc}")
    try:
        from app.services.ai.reranker import _get_cross_encoder

        await loop.run_in_executor(None, _get_cross_encoder)
        logger.info("Reranker warmed up")
    except Exception as exc:
        logger.warning(f"Reranker warmup failed (non-fatal): {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info(
        f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [{settings.APP_ENV}]"
    )

    await run_migrations()
    logger.info("Database migrations applied")

    try:
        redis = await get_redis()
        await redis.ping()
        logger.info("Redis connection verified")
    except Exception as e:
        logger.warning(f"Redis not available: {e}")

    if settings.SKIP_MODEL_WARMUP:
        logger.info("Skipping model warmup (SKIP_MODEL_WARMUP=true)")
    else:
        await _warmup_models()

    yield

    await close_redis()
    logger.info("ChronoLegal shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered Legal Research Platform — ChronoLegal",
    version=settings.APP_VERSION,
    docs_url="/api/docs" if settings.is_development else None,
    redoc_url="/api/redoc" if settings.is_development else None,
    openapi_url="/api/openapi.json" if settings.is_development else None,
    lifespan=lifespan,
)

# --- Middleware (order matters) ---
app.add_middleware(SecurityMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter


# --- Exception Handlers ---
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "type": type(exc).__name__},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "type": "ValidationError"},
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Rate limit exceeded. Please slow down."},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# --- Routes ---
app.include_router(api_router, prefix="/api/v1")
app.include_router(ws_router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
    }


@app.get("/", tags=["Root"])
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/api/docs",
    }
