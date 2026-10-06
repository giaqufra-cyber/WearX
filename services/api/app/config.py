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
    # Connessioni al database per processo (seduta 24). Con il pooler di Supabase in modalità
    # "session" ogni connessione aperta occupa un posto del pool del progetto (15 sul piano
    # gratuito): istanze massime x (pool + extra) + worker deve restarci dentro. Il test di
    # carico mostra che un'istanza satura la CPU ben prima di 5 connessioni occupate.
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=5, ge=0, le=50)

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

    # Da dove leggere l'IP di chi chiama (serve ai limiti per IP):
    # - "none": la connessione (sviluppo);
    # - "google": Cloud Run, ultimo valore di X-Forwarded-For (quello aggiunto da Google;
    #   i valori prima li può scrivere chiunque);
    # - "cloudflare": CF-Connecting-IP, SOLO se l'API è raggiungibile esclusivamente da
    #   Cloudflare (altrimenti l'header è falsificabile).
    proxy_mode: Literal["none", "google", "cloudflare"] = "none"
    # Vecchio nome di proxy_mode="cloudflare" (seduta 2).
    trust_proxy_headers: bool = False

    # Osservabilità (seduta 23). Progetto Google per collegare i log alle tracce; Sentry solo
    # se c'è il DSN; release = commit del deploy.
    gcp_project: str | None = None
    sentry_dsn: SecretStr | None = None
    sentry_traces_sample_rate: float = Field(default=0.0, ge=0, le=1)
    release: str | None = None
    # Su Google Cloud le chiamate alle API Google usano l'identità del servizio (nessuna chiave).
    google_metadata_auth: bool = False

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

    # Google Safe Browsing (liste di siti di phishing e malware) per i link ai negozi.
    # Senza chiave valgono solo i domini bloccati dallo staff.
    safe_browsing_key: SecretStr | None = None

    # Attestazione del dispositivo (seduta 22): App Attest su iOS, Play Integrity su Android.
    # "off": ignorata; "soft": i voti da dispositivi non verificati pesano la metà;
    # "required": senza dispositivo verificato non si vota. In produzione almeno "soft".
    attestation_mode: Literal["off", "soft", "required"] = "off"
    # Identità dell'app: Team ID Apple + bundle id; nome del pacchetto Android.
    apple_team_id: str | None = None
    ios_bundle_id: str = "app.wearx.mobile"
    android_package: str = "app.wearx.mobile"
    # Chiavi App Attest dell'ambiente di sviluppo (build di sviluppo): mai in produzione.
    app_attest_allow_development: bool = True
    # Play Integrity: numero del progetto Google Cloud (pubblico, va anche nell'app) e account
    # di servizio (JSON) che può decifrare i verdetti. L'account di servizio è SEGRETO.
    play_integrity_project_number: str | None = None
    google_service_account_json: SecretStr | None = None

    # Pagine dell'app negli store (schermata "Aggiorna l'app").
    ios_store_url: str | None = None
    android_store_url: str | None = None

    # Versione dei termini che l'app mostra in registrazione.
    terms_version: str = "2026-10"
    # Pagine legali (seduta 24): servite dall'API su /legal/... finché non c'è il sito.
    # Vuoto = public_api_url + "/legal". Con il sito: es. "https://wearx.app".
    legal_base_url: str = ""
    # Riquadro "Bozza, da far rivedere a un legale" in cima alle pagine: false dopo la revisione.
    legal_draft: bool = True

    # Feature flag esposti all'app via /v1/config.
    feature_flags: dict[str, bool] = Field(
        default_factory=lambda: {
            "insights": True,
            "business_accounts": True,
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
    """Configurazione; i controlli qui valgono per ogni componente (API, worker, worker link)."""
    settings = Settings()
    if settings.is_production and settings.age_provider == "fake":
        raise RuntimeError("WEARX_AGE_PROVIDER: il fornitore finto non è ammesso in produzione")
    if settings.is_production and settings.attestation_mode == "off":
        raise RuntimeError("WEARX_ATTESTATION_MODE: in produzione almeno 'soft'")
    if settings.is_production and settings.app_attest_allow_development:
        raise RuntimeError("WEARX_APP_ATTEST_ALLOW_DEVELOPMENT va spento in produzione")
    if settings.env in ("staging", "production") and not settings.staff_require_mfa:
        raise RuntimeError("WEARX_STAFF_REQUIRE_MFA non può essere spento in staging/produzione")
    return settings


Component = Literal["api", "worker", "linkcheck"]


def require_secrets(settings: Settings, component: Component) -> None:
    """In produzione ogni componente parte solo con i SUOI segreti (seduta 23: ogni servizio
    riceve solo quelli che usa, per esempio il worker dei link non ha le chiavi dell'archivio)."""
    if not settings.is_production:
        return
    missing: list[str] = []
    if component in ("api", "worker"):
        if settings.vote_pepper.get_secret_value().startswith("local-"):
            missing.append("WEARX_VOTE_PEPPER")
        if settings.storage_secret_key.get_secret_value().startswith("wearx-local"):
            missing.append("WEARX_STORAGE_SECRET_KEY")
    if component == "api":
        if settings.age_webhook_secret.get_secret_value().startswith("local-"):
            missing.append("WEARX_AGE_WEBHOOK_SECRET")
        if settings.proxy_mode == "none" and not settings.trust_proxy_headers:
            missing.append("WEARX_PROXY_MODE ('google' o 'cloudflare')")
    if component == "worker":
        if settings.supabase_secret_key is None:
            missing.append("WEARX_SUPABASE_SECRET_KEY")
        if settings.push_provider != "expo":
            missing.append("WEARX_PUSH_PROVIDER=expo")
    if missing:
        raise RuntimeError(f"Configurazione di produzione incompleta ({component}): {missing}")
