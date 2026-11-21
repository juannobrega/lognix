"""Configuração vinda do ambiente (.env). Só o que precisa existir antes do primeiro login."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    lognix_secret_key: str = Field(alias="LOGNIX_SECRET_KEY")
    lognix_public_url: str = Field(default="http://localhost:8080", alias="LOGNIX_PUBLIC_URL")
    lognix_log_level: str = Field(default="INFO", alias="LOGNIX_LOG_LEVEL")

    database_url: str = Field(
        default="postgresql+asyncpg://lognix:lognix@localhost:5432/lognix", alias="DATABASE_URL"
    )

    loki_url: str = Field(default="http://loki:3100", alias="LOKI_URL")
    loki_retention_days: int = Field(default=15, alias="LOKI_RETENTION_DAYS")
    alloy_url: str = Field(default="http://alloy:12345", alias="ALLOY_URL")
    alloy_config_path: str = Field(default="/alloy-config/config.alloy", alias="ALLOY_CONFIG_PATH")
    tunnels_dir: str = Field(default="/tunnels", alias="TUNNELS_DIR")

    access_token_ttl_seconds: int = Field(default=15 * 60, alias="LOGNIX_ACCESS_TTL")
    refresh_token_ttl_seconds: int = Field(default=7 * 24 * 3600, alias="LOGNIX_REFRESH_TTL")
    login_rate_limit_per_minute: int = Field(default=10, alias="LOGNIX_LOGIN_RATE_LIMIT")

    @field_validator("lognix_secret_key")
    @classmethod
    def _secret_long_enough(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("LOGNIX_SECRET_KEY precisa ter pelo menos 32 caracteres")
        return value

    @property
    def cookie_secure(self) -> bool:
        return self.lognix_public_url.startswith("https://")


@lru_cache
def get_settings() -> Settings:
    return Settings()
