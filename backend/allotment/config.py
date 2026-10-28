import os
from datetime import timedelta


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
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_MB", "200")) * 1024 * 1024
    MEDIA_URL_TTL_SECONDS = 3600
    # Encrypts stored third-party tokens (Fernet key material is derived from this).
    # Falls back to JWT_SECRET_KEY; set it separately so rotating one doesn't break the other.
    TOKEN_ENCRYPTION_KEY = os.environ.get("TOKEN_ENCRYPTION_KEY")
    # Mastodon: allow http/private-network instances (local dev only), batching of photo posts
    # (seconds to wait so a burst of uploads becomes one post) and when the daily digest goes out.
    FEDIVERSE_ALLOW_PRIVATE_HOSTS = os.environ.get("FEDIVERSE_ALLOW_PRIVATE_HOSTS") == "1"
    MASTODON_PHOTO_BATCH_SECONDS = int(os.environ.get("MASTODON_PHOTO_BATCH_SECONDS", "180"))
    MASTODON_DIGEST_HOUR_UTC = int(os.environ.get("MASTODON_DIGEST_HOUR_UTC", "19"))
    OTEL_EXPORTER_OTLP_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-only-insecure-secret-change-me-in-prod")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=30)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
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
    STORAGE_BACKEND = "file"
    CELERY_ALWAYS_EAGER = True
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    SQLALCHEMY_DATABASE_URI = _test_database_url()
    OTEL_EXPORTER_OTLP_ENDPOINT = None
    FEDIVERSE_ALLOW_PRIVATE_HOSTS = True  # tests mock HTTP; a dedicated test covers the block
    MASTODON_PHOTO_BATCH_SECONDS = 0
