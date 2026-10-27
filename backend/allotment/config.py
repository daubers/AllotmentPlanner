import os
from datetime import timedelta


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://allotment:allotment@db:5432/allotment"
    )
    REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL", "http://minio:9000")
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
    SQLALCHEMY_DATABASE_URI = _test_database_url()
    OTEL_EXPORTER_OTLP_ENDPOINT = None
