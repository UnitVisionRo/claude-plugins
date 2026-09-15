"""Single source of runtime configuration, read from `.env` (gitignored)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str
    TEST_DB_NAME: str = ""
    
    SESSION_TTL_HOURS: int = 12
    COOKIE_SECURE: bool = True  # True in any deployed environment (HTTPS); False only for local dev

    REST_CORS_ORIGINS: str = ""
    API_KEYS: str = ""

    @property
    def rest_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.REST_CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def api_keys(self) -> set[str]:
        return {key.strip() for key in self.API_KEYS.split(",") if key.strip()}


settings = Settings()  # type: ignore[call-arg]
