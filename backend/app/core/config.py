from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    LLM_PROVIDER: Literal["ollama", "openai", "anthropic", "huggingface"] = "ollama"
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

    # Embeddings
    EMBEDDING_MODEL: str = "BAAI/bge-large-en-v1.5"
    EMBEDDING_BACKUP_MODEL: str = "nlpaueb/legal-bert-base-uncased"
    EMBEDDING_DIMENSION: int = 1024
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_DEVICE: str = "cpu"

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
    return Settings()


settings = get_settings()
