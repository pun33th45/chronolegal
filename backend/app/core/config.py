from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Values shipped in .env.example — forbidden in production
_DEFAULT_SECRETS: frozenset[str] = frozenset(
    {
        "your-super-secret-key-change-in-production-min-32-chars",
        "your-jwt-secret-key-change-in-production",
        "chronolegal_password",
        "redis_password",
        "",
    }
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "ChronoLegal"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_VERSION: str = "1.0.0"
    APP_PORT: int = 8000
    APP_HOST: str = "0.0.0.0"
    SECRET_KEY: str
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Database
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "chronolegal"
    POSTGRES_USER: str = "chronolegal_user"
    POSTGRES_PASSWORD: str = "chronolegal_password"
    DATABASE_URL: str = ""
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def build_database_url(cls, v: str, info) -> str:
        if v:
            return v
        data = info.data
        return (
            f"postgresql+asyncpg://{data.get('POSTGRES_USER')}:"
            f"{data.get('POSTGRES_PASSWORD')}@{data.get('POSTGRES_HOST')}:"
            f"{data.get('POSTGRES_PORT')}/{data.get('POSTGRES_DB')}"
        )

    # ChromaDB
    # "http": connect to an external Chroma server (self-hosted Docker
    # Compose default — unchanged). "embedded": run Chroma in-process against
    # local disk (CHROMA_PERSIST_DIRECTORY) — for hosts with no separate
    # Chroma service, e.g. a free-tier PaaS demo deployment.
    CHROMA_MODE: Literal["http", "embedded"] = "http"
    CHROMA_HOST: str = "chromadb"
    CHROMA_PORT: int = 8001
    CHROMA_COLLECTION_NAME: str = "legal_documents"
    CHROMA_PERSIST_DIRECTORY: str = "/data/chromadb"

    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = "redis_password"
    REDIS_DB: int = 0
    REDIS_URL: str = ""
    CACHE_TTL_SECONDS: int = 3600

    @field_validator("REDIS_URL", mode="before")
    @classmethod
    def build_redis_url(cls, v: str, info) -> str:
        if v:
            return v
        data = info.data
        return (
            f"redis://:{data.get('REDIS_PASSWORD')}@{data.get('REDIS_HOST')}:"
            f"{data.get('REDIS_PORT')}/{data.get('REDIS_DB')}"
        )

    # JWT
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    @field_validator("JWT_SECRET_KEY", mode="before")
    @classmethod
    def use_secret_key_fallback(cls, v: str, info) -> str:
        return v or info.data.get("SECRET_KEY", "")

    # LLM
    LLM_PROVIDER: Literal["ollama", "openai", "anthropic", "huggingface", "groq"] = (
        "ollama"
    )
    LLM_MODEL: str = "llama3.1:8b"
    LLM_BASE_URL: str = "http://ollama:11434"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 2048
    LLM_TIMEOUT_SECONDS: int = 120

    OLLAMA_HOST: str = "ollama"
    OLLAMA_PORT: int = 11434
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-haiku-4-5-20251001"
    GROQ_API_KEY: str = ""
    # openai/gpt-oss-20b: verified via a real, live Groq API call (not just
    # constructibility) as of this writing — llama-3.1-8b-instant, the
    # previous default, no longer exists in Groq's live model catalog.
    # gpt-oss is a reasoning model but keeps its chain-of-thought in a
    # separate response field (unlike e.g. qwen/qwen3.6-27b, which was
    # also tested and inlines raw <think> tags into the visible answer
    # content — unsuitable here). Groq's hosted-model lineup changes over
    # time; confirm this is still current before relying on live inference.
    GROQ_MODEL: str = "openai/gpt-oss-20b"

    # Embeddings
    # "huggingface": load EMBEDDING_MODEL locally via sentence-transformers
    # (self-hosted default — unchanged). "openai": call OpenAI's embedding
    # API instead — avoids loading a ~1.3GB model into process memory, for
    # hosts with a tight RAM ceiling, e.g. a free-tier PaaS demo deployment.
    EMBEDDING_PROVIDER: Literal["huggingface", "openai"] = "huggingface"
    EMBEDDING_MODEL: str = "BAAI/bge-large-en-v1.5"
    EMBEDDING_BACKUP_MODEL: str = "nlpaueb/legal-bert-base-uncased"
    EMBEDDING_DIMENSION: int = 1024
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_DEVICE: str = "cpu"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # RAG
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 128
    TOP_K_RETRIEVAL: int = 12
    TOP_K_RERANKED: int = 5
    SIMILARITY_THRESHOLD: float = 0.6
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Hybrid search (BM25 + dense fused with Reciprocal Rank Fusion)
    HYBRID_SEARCH: bool = True
    HYBRID_RRF_K: int = 60  # RRF constant; higher = smoother rank fusion

    # Dataset
    CHRONOLEGAL_DATA_PATH: str = "/data/chronolegal"
    PROCESSED_DATA_PATH: str = "/data/processed"
    EMBEDDINGS_BATCH_SIZE: int = 64

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 500
    RATE_LIMIT_PER_DAY: int = 2000

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    CORS_ALLOW_CREDENTIALS: bool = True

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # Storage
    UPLOAD_DIR: str = "/data/uploads"
    MAX_UPLOAD_SIZE_MB: int = 50

    # Monitoring
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090

    # Startup — skips the embedding-model/reranker warmup in app startup's
    # lifespan (see app/main.py). The models are never pre-baked into the
    # Docker image, so a cold container downloads them from HuggingFace on
    # first boot, which can take minutes; CI's Docker runtime smoke test
    # (verifying migrations/Redis/health wiring, not model loading) sets
    # this to skip that download entirely. Defaults to False so normal
    # deployments still get the first-request latency benefit of warmup.
    SKIP_MODEL_WARMUP: bool = False

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> "Settings":
        if self.APP_ENV != "production":
            return self
        insecure: list[str] = []
        checks = {
            "SECRET_KEY": self.SECRET_KEY,
            "JWT_SECRET_KEY": self.JWT_SECRET_KEY,
            "POSTGRES_PASSWORD": self.POSTGRES_PASSWORD,
            "REDIS_PASSWORD": self.REDIS_PASSWORD,
        }
        for name, value in checks.items():
            if value in _DEFAULT_SECRETS:
                insecure.append(name)
        if insecure:
            raise ValueError(
                f"Production startup blocked — insecure default values detected for: "
                f"{', '.join(insecure)}. Update these in your .env file."
            )

        # CORSMiddleware reflects the request's actual Origin back (rather than
        # a literal "*") whenever allow_credentials=True, so this combination
        # isn't "insecure but functional" like a default secret — it's "any
        # site on the internet, with credentials". Block it outright.
        if "*" in self.cors_origins_list and self.CORS_ALLOW_CREDENTIALS:
            raise ValueError(
                'Production startup blocked — CORS_ORIGINS="*" combined with '
                "CORS_ALLOW_CREDENTIALS=true allows credentialed requests from "
                "any origin. Set CORS_ORIGINS to the exact production domain(s)."
            )

        # DEBUG isn't a secret so it isn't in _DEFAULT_SECRETS, but it isn't
        # cosmetic either: it enables SQL echo (database.py) and loguru
        # diagnose/backtrace (logging.py), both of which can write request
        # data and local variable values (potentially including PII or
        # hashed credentials) into server-side logs.
        if self.DEBUG:
            raise ValueError(
                "Production startup blocked — DEBUG=true enables SQL statement "
                "echo and verbose exception logging, both of which can write "
                "sensitive data to server logs. Set DEBUG=false in production."
            )

        return self

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def ollama_base_url(self) -> str:
        return f"http://{self.OLLAMA_HOST}:{self.OLLAMA_PORT}"


@lru_cache
def get_settings() -> Settings:
    # pydantic-settings' BaseSettings.__init__ populates required fields
    # (e.g. SECRET_KEY) from environment variables / .env at runtime; mypy
    # can't see that without the pydantic.mypy plugin, which was tested and
    # caused mypy to hang (2min+, vs ~20s normally) on this codebase.
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
