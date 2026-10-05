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
    # Chiave segreta di Supabase: SOLO sul server (secret manager), mai nell'app. Serve a
    # cancellare l'utente di Supabase Auth alla fine dei 30 giorni di una cancellazione.
    supabase_secret_key: SecretStr | None = None
    jwt_audience: str = "authenticated"
    jwt_algorithms: tuple[str, ...] = ("ES256", "RS256")
    # Supabase mette in cache il JWKS per 10 minuti: non conviene tenerlo più a lungo.
    jwks_cache_seconds: int = 600
    # Tolleranza sull'orologio per exp/iat.
    jwt_leeway_seconds: int = 30

    # Staff di moderazione: serve il secondo fattore (Supabase MFA, claim aal = "aal2").
    # Si può spegnere solo in locale e nei test; in staging e produzione è sempre richiesto.
    staff_require_mfa: bool = True
    # Origini del pannello web dello staff ammesse da CORS (es. https://admin.wearx.app).
    admin_origins: list[str] = Field(default_factory=list)

    # Dietro Cloudflare l'IP reale arriva in CF-Connecting-IP. Va attivato SOLO se l'API
    # è raggiungibile esclusivamente attraverso il proxy, altrimenti l'header è falsificabile.
    trust_proxy_headers: bool = False

    # Verifica dell'età (sez. 11.2). Il fornitore vero si sceglie con la decisione D5;
    # "fake" simula il fornitore (pagina di prova + webhook firmato) e in produzione è vietato.
    age_provider: Literal["fake"] = "fake"
    # Segreto condiviso con il fornitore per firmare i webhook (HMAC-SHA256).
    age_webhook_secret: SecretStr = Field(default=SecretStr("local-only-age-webhook"))
    # Tolleranza sul timestamp della firma: oltre, il webhook è rifiutato (anti-replay).
    age_webhook_tolerance_seconds: int = 300
    # Una verifica non completata entro questo tempo scade.
    age_session_ttl_seconds: int = 3600
    # Indirizzo pubblico dell'API (serve alla pagina di prova del fornitore finto).
    public_api_url: str = "http://localhost:8000"

    # Archivio delle foto, compatibile S3 (Cloudflare R2 / S3 in produzione, MinIO o
    # moto_server in locale). Bucket PRIVATO: le foto si leggono solo con URL firmati.
    storage_endpoint_url: str | None = "http://localhost:9000"
    # Indirizzo che il telefono usa per caricare/leggere (se diverso da quello interno).
    storage_public_url: str | None = None
    storage_region: str = "us-east-1"
    storage_bucket: str = "wearx-media"
    storage_access_key: str = "wearx"
    storage_secret_key: SecretStr = Field(default=SecretStr("wearx-local-only"))
    # Limiti del caricamento.
    upload_max_bytes: int = 15 * 1024 * 1024
    upload_url_ttl_seconds: int = 900
    media_url_ttl_seconds: int = 3600
    max_pending_uploads: int = 20

    # Push: "expo" spedisce davvero (servizio push di Expo), "log" li scrive solo nei log
    # (sviluppo e test). Il token di accesso Expo è facoltativo ma consigliato: con la
    # "sicurezza avanzata" attiva nel progetto Expo, senza token nessuno può mandare push.
    push_provider: Literal["expo", "log"] = "log"
    expo_access_token: SecretStr | None = None

    # Versione dei termini che l'app mostra in registrazione.
    terms_version: str = "2026-10"

    # Feature flag esposti all'app via /v1/config.
    feature_flags: dict[str, bool] = Field(
        default_factory=lambda: {
            "insights": True,
            "business_accounts": False,
            "capsules": False,
            "spid_cie": False,
        }
    )

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def age_return_schemes(self) -> tuple[str, ...]:
        """Indirizzi a cui il fornitore può riportare l'utente (niente redirect aperti)."""
        if self.env in ("staging", "production"):
            return ("wearx://",)
        # exp:// è Expo Go; localhost:8081 l'anteprima web: solo per lo sviluppo.
        if self.env == "dev":
            return ("wearx://", "exp://")
        return ("wearx://", "exp://", "http://localhost:8081/")

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
    if settings.is_production and settings.age_provider == "fake":
        raise RuntimeError("WEARX_AGE_PROVIDER: il fornitore finto non è ammesso in produzione")
    age_secret = settings.age_webhook_secret.get_secret_value()
    if settings.is_production and age_secret.startswith("local-"):
        raise RuntimeError("WEARX_AGE_WEBHOOK_SECRET non impostato in produzione")
    storage_secret = settings.storage_secret_key.get_secret_value()
    if settings.is_production and storage_secret.startswith("wearx-local"):
        raise RuntimeError("WEARX_STORAGE_SECRET_KEY non impostato in produzione")
    if settings.is_production and settings.supabase_secret_key is None:
        raise RuntimeError("WEARX_SUPABASE_SECRET_KEY non impostato in produzione")
    if settings.is_production and settings.push_provider != "expo":
        raise RuntimeError("WEARX_PUSH_PROVIDER deve essere 'expo' in produzione")
    if settings.env in ("staging", "production") and not settings.staff_require_mfa:
        raise RuntimeError("WEARX_STAFF_REQUIRE_MFA non può essere spento in staging/produzione")
    return settings
