"""Application settings shared by the Stage 1 backend skeleton."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_name: str = "flux-platform-api"
    environment: str = "local"
    api_host: str = "0.0.0.0"
    api_port: int = 8000


def load_settings() -> Settings:
    return Settings(
        environment=os.getenv("ENVIRONMENT", "local"),
        api_host=os.getenv("API_HOST", "0.0.0.0"),
        api_port=int(os.getenv("API_PORT", "8000")),
    )
