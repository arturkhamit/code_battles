from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: Literal["production", "local"] = "production"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Required, no default: the runner starts containers for whoever holds this token.
    RUNNER_TOKEN: str = Field(min_length=32)

    # Where Docker is. In production this is the socket proxy, never the socket itself:
    # tcp://docker-proxy:2375. On a laptop without the proxy: unix:///var/run/docker.sock
    SANDBOX_DOCKER_URL: str = "unix:///var/run/docker.sock"
    # Fixed on purpose: negotiating needs GET /version, which the proxy does not allow.
    SANDBOX_DOCKER_API_VERSION: str = "1.44"
    SANDBOX_PYTHON_IMAGE: str = "code-battles-sandbox-python:1"
    SANDBOX_CPP_IMAGE: str = "code-battles-sandbox-cpp:1"
    SANDBOX_CPUS: float = Field(1.0, ge=0.5, le=1.0)  # per container

    RUNNER_MAX_CONCURRENCY: int = Field(4, ge=1, le=64)  # containers at once on the whole server
    RUNNER_QUEUE_TIMEOUT_SECONDS: float = Field(20.0, ge=0)  # how long a request waits for a slot

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def _token_is_real(self):
        if self.ENVIRONMENT == "production" and self.RUNNER_TOKEN.startswith("change-me"):
            raise ValueError("RUNNER_TOKEN is still the placeholder from .env.example")
        return self
