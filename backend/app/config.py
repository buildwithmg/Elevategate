from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration, loaded from environment variables (or a .env file in development).

    Security-sensitive values (JWT secret, Ed25519 private key material, enrollment key) are
    read here from the environment/mounted files only — never hard-coded, never persisted to the
    database. See docs/BACKEND_THREAT_MODEL.md.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"

    # SQLAlchemy 2's psycopg (v3) dialect serves both the async app engine and Alembic's sync
    # engine from the same URL scheme (postgresql+psycopg://...) - no separate sync/async URL.
    database_url: str = "postgresql+psycopg://localhost/elevategate"

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30

    # Exactly one of these must be set; enforced lazily in app.core.signing (not here) so that
    # contexts which never sign anything (e.g. Alembic) don't need the key configured at all.
    ed25519_private_key_path: str | None = None
    ed25519_private_key_b64: str | None = None

    # How long an issued approval token remains valid. Requirement: "Approval expires after 5
    # minutes by default."
    approval_ttl_seconds: int = 300

    # How long an elevation request stays open for admin review before it auto-expires (distinct
    # from approval_ttl_seconds, which times out the signed token *after* approval).
    elevation_request_ttl_seconds: int = 3600

    # Pre-shared secret an agent must present (via the X-Enrollment-Key header) to enroll a new
    # device. Closes off open self-enrollment - see docs/BACKEND_THREAT_MODEL.md.
    enrollment_key: str

    # A device counts as "online" (GET /devices, GET /dashboard/summary) iff it's actively
    # enrolled and its last heartbeat/request was within this many seconds.
    device_online_threshold_seconds: int = 300

    # Rate limits (slowapi / "N/minute" syntax) for device-facing endpoints.
    rate_limit_enroll: str = "5/minute"
    rate_limit_heartbeat: str = "30/minute"
    rate_limit_elevation_request_submit: str = "10/minute"
    rate_limit_agent_decisions: str = "20/minute"
    rate_limit_approval_consumed: str = "20/minute"
    rate_limit_login: str = "10/minute"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # required fields come from the environment
