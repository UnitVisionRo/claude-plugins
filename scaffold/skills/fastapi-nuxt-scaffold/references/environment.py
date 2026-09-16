"""Single source of runtime configuration, read from `.env` (gitignored)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "__APP_NAME__"
    DEBUG: bool = False

    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str
    TEST_DB_NAME: str = ""

    # Signs JWTs, keys the HMAC fingerprints of refresh/invite tokens, and derives the Fernet
    # key that encrypts stored TOTP secrets. No default on purpose: a shipped default key is a
    # shipped forgery oracle. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(64))"`.
    # Rotating it invalidates every session, every pending invite, and every enrolled TOTP secret.
    TOKEN_KEY: str

    ACCESS_TOKEN_EXP_MINUTES: int = 30
    REFRESH_TOKEN_EXP_DAYS: int = 30
    # A refresh token unused for this long is dead even if it hasn't formally expired.
    REFRESH_TOKEN_IDLE_DAYS: int = 7

    # How long a password-reset link stays usable. Short on purpose: it arrives by email, and
    # email is the least trustworthy place a live credential can sit.
    RECOVERY_TOKEN_EXP_MINUTES: int = 30

    COOKIE_SECURE: bool = True  # True in any deployed environment (HTTPS); False only for local dev
    COOKIE_SAMESITE: str = "lax"

    # Where the browser reaches the frontend -- used to build invite links in emails.
    FRONTEND_BASE_URL: str = "http://localhost:3000"

    REST_CORS_ORIGINS: str = ""
    API_KEYS: str = ""

    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = "noreply@example.com"
    MAIL_FROM_NAME: str = "__APP_NAME__"
    MAIL_SERVER: str = "localhost"
    MAIL_PORT: int = 25
    MAIL_STARTTLS: bool = False
    MAIL_SSL_TLS: bool = False
    MAIL_USE_CREDENTIALS: bool = False
    MAIL_VALIDATE_CERTS: bool = False
    MAIL_TIMEOUT: int = 10

    @property
    def rest_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.REST_CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def api_keys(self) -> set[str]:
        return {key.strip() for key in self.API_KEYS.split(",") if key.strip()}


settings = Settings()  # type: ignore[call-arg]
