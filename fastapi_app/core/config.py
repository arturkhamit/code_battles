from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Battle Engine FastAPI"
    REDIS_URL: str = "redis://localhost:6379/0"
    DJANGO_API_URL: str = "http://localhost:8000/api/internal"

    SECRET_KEY: str = Field(alias="DJANGO_SECRET_KEY")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
