import json
import os
from datetime import timedelta

import structlog

_log = structlog.get_logger(__name__)

# Where "sign in with ..." can send people: a standard OpenID Connect issuer, or a preset.
OIDC_PRESETS = {
    "google": {"name": "Google", "issuer": "https://accounts.google.com"},
    # {tenant} is a tenant id, or "organizations" / "consumers". Not "common": its tokens name the
    # real tenant, so they would not match the issuer.
    "microsoft": {"name": "Microsoft", "issuer": "https://login.microsoftonline.com/{tenant}/v2.0"},
}


def parse_oidc_providers(raw: str | None) -> list[dict]:
    """Read the OIDC_PROVIDERS setting (a JSON list) into complete provider entries.

    An entry that is incomplete is skipped with a warning, so a typo never takes the server down.
    """
    if not raw or not raw.strip():
        return []
    try:
        entries = json.loads(raw)
        if not isinstance(entries, list):
            raise ValueError("expected a list")
    except ValueError as exc:
        _log.warning("oidc_providers_invalid", error=str(exc))
        return []
    providers = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        preset = OIDC_PRESETS.get(str(entry.get("preset", "")).lower(), {})
        issuer = entry.get("issuer") or preset.get("issuer", "")
        needs_tenant = "{tenant}" in issuer
        tenant = str(entry.get("tenant", "")).strip("/ ")
        if needs_tenant and tenant:
            issuer = issuer.replace("{tenant}", tenant)
        provider = {
            "id": str(entry.get("id") or entry.get("preset") or "").lower(),
            "name": entry.get("name") or preset.get("name") or str(entry.get("id", "")),
            "issuer": issuer.rstrip("/"),
            "client_id": entry.get("client_id", ""),
            "client_secret": entry.get("client_secret", ""),
            "scopes": entry.get("scopes") or "openid email profile",
        }
        missing = [k for k in ("id", "issuer", "client_id", "client_secret") if not provider[k]]
        if missing or (needs_tenant and not tenant) or "//" not in issuer:
            _log.warning(
                "oidc_provider_skipped",
                id=provider["id"],
                missing=missing + (["tenant"] if needs_tenant and not tenant else []),
            )
            continue
        if any(p["id"] == provider["id"] for p in providers):
            _log.warning("oidc_provider_duplicate", id=provider["id"])
            continue
        providers.append(provider)
    return providers


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://allotment:allotment@db:5432/allotment"
    )
    REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "file")  # "file" or "s3"
    MEDIA_ROOT = os.environ.get("MEDIA_ROOT", "/data/media")
    S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL")  # None = AWS
    S3_BUCKET = os.environ.get("S3_BUCKET", "allotment-media")
    S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY")
    S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY")
    # Big enough for a GoPro chapter (they split at 4 GB). Keep the frontend's nginx
    # `client_max_body_size` (frontend/nginx.conf) at least this large.
    MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "4096"))
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024
    MEDIA_URL_TTL_SECONDS = 3600
    # Encrypts stored third-party tokens (Fernet key material is derived from this).
    # Falls back to JWT_SECRET_KEY; set it separately so rotating one doesn't break the other.
    TOKEN_ENCRYPTION_KEY = os.environ.get("TOKEN_ENCRYPTION_KEY")
    # Mastodon: allow http/private-network instances (local dev only), batching of photo posts
    # (seconds to wait so a burst of uploads becomes one post) and when the daily digest goes out.
    FEDIVERSE_ALLOW_PRIVATE_HOSTS = os.environ.get("FEDIVERSE_ALLOW_PRIVATE_HOSTS") == "1"
    MASTODON_PHOTO_BATCH_SECONDS = int(os.environ.get("MASTODON_PHOTO_BATCH_SECONDS", "180"))
    MASTODON_DIGEST_HOUR_UTC = int(os.environ.get("MASTODON_DIGEST_HOUR_UTC", "19"))
    # Map from photos (OpenSfM + GDAL, run by the separate `mapper` worker)
    MAPPING_MAX_IMAGES = int(os.environ.get("MAPPING_MAX_IMAGES", "150"))
    MAPPING_VIDEO_FRAMES_PER_SECOND = float(os.environ.get("MAPPING_VIDEO_FPS", "1"))
    MAPPING_MAX_FRAMES_PER_VIDEO = int(os.environ.get("MAPPING_MAX_FRAMES_PER_VIDEO", "60"))
    MAPPING_TIMEOUT_SECONDS = int(os.environ.get("MAPPING_TIMEOUT_SECONDS", "7200"))
    # Photos looked at for objects (about 15 s each on a CPU); video frames fill any spare room.
    MAPPING_DETECT_MAX_SHOTS = int(os.environ.get("MAPPING_DETECT_MAX_SHOTS", "40"))
    # Objects further than this from the camera are ignored: their position and size are too vague.
    MAPPING_DETECT_MAX_RANGE_M = float(os.environ.get("MAPPING_DETECT_MAX_RANGE_M", "15"))
    MAPPING_TILE_TOKEN_TTL_SECONDS = 6 * 3600
    OTEL_EXPORTER_OTLP_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    # Warnings, errors and task outcomes are also kept in the database for the admin page.
    LOG_TO_DB = os.environ.get("LOG_TO_DB", "1") == "1"
    LOG_RETENTION_DAYS = int(os.environ.get("LOG_RETENTION_DAYS", "14"))
    # How long a built data export can be downloaded before it is deleted.
    ACCOUNT_EXPORT_TTL_HOURS = int(os.environ.get("ACCOUNT_EXPORT_TTL_HOURS", "48"))
    APP_VERSION = os.environ.get("APP_VERSION", "dev")
    # Bumped when the API changes in a way an older server cannot serve to a newer app. The phone
    # app says "update the server" when it needs a higher level than this.
    API_LEVEL = 1
    # The oldest phone app this server will work with; older ones are told to update. The default
    # accepts every app.
    MIN_APP_VERSION = os.environ.get("MIN_APP_VERSION", "0.0.0")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-only-insecure-secret-change-me-in-prod")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=30)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    # "open": anyone who can reach the server may register. "invite": only the very first account
    # (to bootstrap an empty server) and people holding an invite from an allotment owner.
    REGISTRATION = os.environ.get("REGISTRATION", "open").lower()
    INVITE_TTL_DAYS = int(os.environ.get("INVITE_TTL_DAYS", "7"))
    # Single sign-on. OIDC_PROVIDERS is a JSON list, e.g.
    #   [{"id": "authentik", "name": "Authentik",
    #     "issuer": "https://auth.example.com/application/o/allotment/",
    #     "client_id": "...", "client_secret": "..."},
    #    {"preset": "google", "client_id": "...", "client_secret": "..."}]
    # Register {PUBLIC_URL}/api/v1/auth/oidc/<id>/callback as the redirect URI at each provider.
    OIDC_PROVIDERS = parse_oidc_providers(os.environ.get("OIDC_PROVIDERS"))
    # The address people use to reach the site (https://plot.example.com); redirect URIs use it.
    PUBLIC_URL = os.environ.get("PUBLIC_URL", "").rstrip("/")
    # Where the phone app may be sent back to after signing in (comma separated).
    OIDC_MOBILE_REDIRECTS = [
        u.strip()
        for u in os.environ.get("OIDC_MOBILE_REDIRECTS", "allotment://auth").split(",")
        if u.strip()
    ]
    OIDC_STATE_TTL_SECONDS = 600
    OIDC_CODE_TTL_SECONDS = 60
    API_TITLE = "Allotment Planner API"
    API_VERSION = "v1"
    OPENAPI_VERSION = "3.0.3"
    OPENAPI_URL_PREFIX = "/api"
    OPENAPI_JSON_PATH = "openapi.json"
    OPENAPI_SWAGGER_UI_PATH = "docs"
    OPENAPI_SWAGGER_UI_URL = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"


def _test_database_url() -> str:
    """A separate database from dev so tests can create/drop tables freely."""
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    return Config.SQLALCHEMY_DATABASE_URI.rsplit("/", 1)[0] + "/allotment_test"


class TestConfig(Config):
    TESTING = True
    LOG_TO_DB = False  # a test that needs it turns it on
    STORAGE_BACKEND = "file"
    CELERY_ALWAYS_EAGER = True
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    SQLALCHEMY_DATABASE_URI = _test_database_url()
    OTEL_EXPORTER_OTLP_ENDPOINT = None
    FEDIVERSE_ALLOW_PRIVATE_HOSTS = True  # tests mock HTTP; a dedicated test covers the block
    MASTODON_PHOTO_BATCH_SECONDS = 0
