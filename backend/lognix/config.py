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

    # Loki e Alloy rodam dentro da imagem e escutam só em localhost (ADR 013). O padrão descreve
    # essa topologia: apontar para um nome de serviço do compose faria a imagem depender de um
    # arranjo externo que ela mesma não cria.
    loki_url: str = Field(default="http://127.0.0.1:3100", alias="LOKI_URL")
    loki_retention_days: int = Field(default=15, alias="LOKI_RETENTION_DAYS")
    alloy_url: str = Field(default="http://127.0.0.1:12345", alias="ALLOY_URL")
    alloy_config_path: str = Field(default="/alloy-config/config.alloy", alias="ALLOY_CONFIG_PATH")
    tunnels_dir: str = Field(default="/tunnels", alias="TUNNELS_DIR")
    #: Onde o frontend construído foi copiado na imagem. Ausente, a API sobe sem interface.
    frontend_dir: str = Field(default="/app/static", alias="LOGNIX_FRONTEND_DIR")
    #: Arquivo de configuração declarativa. Ver ADR 014.
    config_file: str = Field(default="/config/config.yaml", alias="LOGNIX_CONFIG_FILE")

    # Pool do banco. O padrão do SQLAlchemy (5+10) é pequeno para muitos ciclos simultâneos:
    # os ciclos consomem o pool e a API fica na fila. Medido na fase 0.7.0.
    db_pool_size: int = Field(default=20, alias="LOGNIX_DB_POOL_SIZE")
    db_max_overflow: int = Field(default=10, alias="LOGNIX_DB_MAX_OVERFLOW")
    # Ciclos de análise simultâneos. Acima disso não há ganho: o trabalho é CPU e banco,
    # e a concorrência irrestrita só aumenta a latência da API.
    analysis_concurrency: int = Field(default=8, alias="LOGNIX_ANALYSIS_CONCURRENCY")

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
