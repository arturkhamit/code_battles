from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Battle Engine FastAPI"
    # production: /docs, /redoc and /openapi.json are off. local: on.
    ENVIRONMENT: Literal["production", "local"] = "production"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    REDIS_URL: str = "redis://localhost:6379/0"
    DJANGO_INTERNAL_URL: str = "http://localhost:8000/internal"
    # Comma separated, scheme://host[:port] only. Empty = no cross-origin access.
    CORS_ALLOWED_ORIGINS: Annotated[list[str], NoDecode] = []

    # The sandbox runner (runner/): code is judged there, never in this process. In docker: http://runner:8000
    RUNNER_URL: str = "http://localhost:8002"
    # a run is at most ~75 s (compile 15 + tests 60) plus up to 20 s waiting for a free slot
    RUNNER_TIMEOUT_SECONDS: float = Field(110.0, gt=0)

    # Required, no defaults: startup fails with a validation error naming the field.
    JWT_SIGNING_KEY: str = Field(min_length=1)
    INTERNAL_API_TOKEN: str = Field(min_length=1)
    RUNNER_TOKEN: str = Field(min_length=1)  # Bearer token of the runner; must equal RUNNER_TOKEN there

    # Limits, shared by all workers through Redis.
    MAX_CONCURRENT_RUNS: int = Field(4, ge=1)  # sandbox runs on the whole server
    SUBMIT_COOLDOWN_SECONDS: int = Field(3, ge=0)
    WS_CONNECTS_PER_MINUTE: int = Field(20, ge=1)

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @field_validator("CORS_ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value):
        if isinstance(value, str):
            value = [part.strip() for part in value.split(",") if part.strip()]
        for origin in value:
            parts = urlsplit(origin)
            if (
                parts.scheme not in ("http", "https")
                or not parts.netloc
                or parts.path not in ("", "/")
                or parts.query
                or parts.fragment
            ):
                raise ValueError(
                    f"{origin!r} is not an origin: use scheme://host[:port] (http or https)"
                )
        return [origin.rstrip("/") for origin in value]

    @model_validator(mode="after")
    def _secrets_differ(self):
        secrets = (self.JWT_SIGNING_KEY, self.INTERNAL_API_TOKEN, self.RUNNER_TOKEN)
        if len(set(secrets)) != len(secrets):
            raise ValueError("JWT_SIGNING_KEY, INTERNAL_API_TOKEN and RUNNER_TOKEN must all differ")
        if self.is_production:
            for name in ("JWT_SIGNING_KEY", "INTERNAL_API_TOKEN", "RUNNER_TOKEN"):
                value = getattr(self, name)
                if len(value) < 32 or value.startswith("change-me"):
                    raise ValueError(
                        f"{name} is too weak for production: use 32+ random characters"
                    )
        return self

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def DJANGO_READY_URL(self) -> str:  # noqa: N802
        """Django /ready (checks Postgres and Redis) sits next to /internal, not under it."""
        base = self.DJANGO_INTERNAL_URL.rstrip("/")
        return base.removesuffix("/internal") + "/ready"


settings = Settings()
