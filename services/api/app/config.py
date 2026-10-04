"""Configurazione dell'API, letta solo da variabili d'ambiente (prefisso WEARX_)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WEARX_", env_file=".env", extra="ignore")

    env: Literal["local", "test", "dev", "staging", "production"] = "local"

    # Connessione dell'API: ruolo dedicato con i soli permessi necessari (mai superuser).
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/wearx"
    redis_url: str = "redis://localhost:6379/0"

    # Versione minima dell'app accettata (header X-App-Version). Sotto: 426.
    min_app_version: str = "0.1.0"

    # Segreto per lo pseudonimo dei votanti (HMAC). In produzione arriva dal secret manager.
    vote_pepper: SecretStr = Field(default=SecretStr("local-only-not-a-secret"))

    # Supabase Auth. Token verificati SOLO con chiavi asimmetriche pubblicate nel JWKS.
    # Esempio: https://abcdefgh.supabase.co
    supabase_url: str = "http://localhost:54321"
    jwt_audience: str = "authenticated"
    jwt_algorithms: tuple[str, ...] = ("ES256", "RS256")
    # Supabase mette in cache il JWKS per 10 minuti: non conviene tenerlo più a lungo.
    jwks_cache_seconds: int = 600
    # Tolleranza sull'orologio per exp/iat.
    jwt_leeway_seconds: int = 30

    # Dietro Cloudflare l'IP reale arriva in CF-Connecting-IP. Va attivato SOLO se l'API
    # è raggiungibile esclusivamente attraverso il proxy, altrimenti l'header è falsificabile.
    trust_proxy_headers: bool = False

    # Versione dei termini che l'app mostra in registrazione.
    terms_version: str = "2026-10"

    # Feature flag esposti all'app via /v1/config.
    feature_flags: dict[str, bool] = Field(
        default_factory=lambda: {
            "insights": False,
            "business_accounts": False,
            "capsules": False,
            "spid_cie": False,
        }
    )

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def jwt_issuer(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def jwks_url(self) -> str:
        return f"{self.jwt_issuer}/.well-known/jwks.json"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.is_production and settings.vote_pepper.get_secret_value().startswith("local-"):
        raise RuntimeError("WEARX_VOTE_PEPPER non impostato in produzione")
    return settings
