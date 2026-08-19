"""Application settings."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class PlanLimits:
    rate_limit_per_minute: int
    concurrent_generation_limit: int
    monthly_generation_quota: int


@dataclass(frozen=True)
class Settings:
    app_name: str = "flux-platform-api"
    environment: str = "local"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    frontend_public_url: str = "http://localhost:3001"
    cors_origins: tuple[str, ...] = ("http://localhost:3001",)
    database_url: str = "postgresql+psycopg://flux:flux_local_password@postgres:5432/flux_platform"
    redis_url: str = "redis://redis:6379/0"
    minio_public_endpoint: str = "http://localhost:9000"
    minio_bucket: str = "generations"
    default_model_version: str = "flux2-dev-bf16-v1"
    jwt_secret_key: str = "change-me-before-production"
    jwt_algorithm: str = "HS256"
    api_key_hash_secret: str = "change-me-before-production"
    access_token_expire_minutes: int = 60
    generation_rate_limit_per_minute: int = 10
    concurrent_generation_limit: int = 2
    plan_limits: dict[str, PlanLimits] | None = None
    prompt_presets_path: str = "/app/model_configs/presets.yaml"
    quality_presets_path: str = "/app/model_configs/quality.yaml"
    safety_config_path: str = "/app/model_configs/safety.yaml"
    worker_health_timeout_seconds: float = 2.0


def load_settings() -> Settings:
    frontend_public_url = os.getenv("FRONTEND_PUBLIC_URL", "http://localhost:3001")
    cors_origins = tuple(
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", frontend_public_url).split(",")
        if origin.strip()
    )
    settings = Settings(
        environment=os.getenv("ENVIRONMENT", "local"),
        api_host=os.getenv("API_HOST", "0.0.0.0"),
        api_port=int(os.getenv("API_PORT", "8000")),
        frontend_public_url=frontend_public_url,
        cors_origins=cors_origins,
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://flux:flux_local_password@postgres:5432/flux_platform",
        ),
        redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
        minio_public_endpoint=os.getenv("MINIO_PUBLIC_ENDPOINT", "http://localhost:9000"),
        minio_bucket=os.getenv("MINIO_BUCKET", "generations"),
        default_model_version=os.getenv("DEFAULT_MODEL_VERSION", "flux2-dev-bf16-v1"),
        jwt_secret_key=os.getenv("JWT_SECRET_KEY", "change-me-before-production"),
        jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
        api_key_hash_secret=os.getenv(
            "API_KEY_HASH_SECRET",
            os.getenv("JWT_SECRET_KEY", "change-me-before-production"),
        ),
        access_token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")),
        generation_rate_limit_per_minute=int(os.getenv("GENERATION_RATE_LIMIT_PER_MINUTE", "10")),
        concurrent_generation_limit=int(os.getenv("CONCURRENT_GENERATION_LIMIT", "2")),
        prompt_presets_path=os.getenv("PROMPT_PRESETS_PATH", "/app/model_configs/presets.yaml"),
        quality_presets_path=os.getenv("QUALITY_PRESETS_PATH", "/app/model_configs/quality.yaml"),
        safety_config_path=os.getenv("SAFETY_CONFIG_PATH", "/app/model_configs/safety.yaml"),
        worker_health_timeout_seconds=float(os.getenv("WORKER_HEALTH_TIMEOUT_SECONDS", "2.0")),
        plan_limits={
            "free": PlanLimits(
                rate_limit_per_minute=_env_int(
                    "FREE_GENERATION_RATE_LIMIT_PER_MINUTE",
                    os.getenv("GENERATION_RATE_LIMIT_PER_MINUTE", "10"),
                ),
                concurrent_generation_limit=_env_int(
                    "FREE_CONCURRENT_GENERATION_LIMIT",
                    os.getenv("CONCURRENT_GENERATION_LIMIT", "2"),
                ),
                monthly_generation_quota=int(os.getenv("FREE_MONTHLY_GENERATION_QUOTA", "100")),
            ),
            "pro": PlanLimits(
                rate_limit_per_minute=int(os.getenv("PRO_GENERATION_RATE_LIMIT_PER_MINUTE", "60")),
                concurrent_generation_limit=int(os.getenv("PRO_CONCURRENT_GENERATION_LIMIT", "6")),
                monthly_generation_quota=int(os.getenv("PRO_MONTHLY_GENERATION_QUOTA", "2000")),
            ),
            "team": PlanLimits(
                rate_limit_per_minute=int(os.getenv("TEAM_GENERATION_RATE_LIMIT_PER_MINUTE", "180")),
                concurrent_generation_limit=int(os.getenv("TEAM_CONCURRENT_GENERATION_LIMIT", "12")),
                monthly_generation_quota=int(os.getenv("TEAM_MONTHLY_GENERATION_QUOTA", "10000")),
            ),
        },
    )
    validate_settings(settings)
    return settings


def _env_int(name: str, default: str) -> int:
    return int(os.getenv(name, default))


def validate_settings(settings: Settings) -> None:
    if settings.environment.lower() not in {"production", "prod"}:
        return

    errors: list[str] = []
    if settings.jwt_secret_key == "change-me-before-production" or len(settings.jwt_secret_key) < 32:
        errors.append("JWT_SECRET_KEY must be set to a strong production secret")
    if settings.api_key_hash_secret == "change-me-before-production" or len(settings.api_key_hash_secret) < 32:
        errors.append("API_KEY_HASH_SECRET must be set to a strong production secret")
    if "*" in settings.cors_origins:
        errors.append("CORS_ORIGINS must not contain '*' in production")
    if not settings.database_url:
        errors.append("DATABASE_URL is required")
    if not settings.redis_url:
        errors.append("REDIS_URL is required")
    if not settings.minio_public_endpoint:
        errors.append("MINIO_PUBLIC_ENDPOINT is required")

    if errors:
        raise RuntimeError("Invalid production settings: " + "; ".join(errors))


def limits_for_plan(settings: Settings, plan: str) -> PlanLimits:
    plan_limits = settings.plan_limits or {}
    return plan_limits.get(
        plan,
        PlanLimits(
            rate_limit_per_minute=settings.generation_rate_limit_per_minute,
            concurrent_generation_limit=settings.concurrent_generation_limit,
            monthly_generation_quota=int(os.getenv("MONTHLY_GENERATION_QUOTA", "100")),
        ),
    )
