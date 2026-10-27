import os


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://allotment:allotment@db:5432/allotment"
    )
    REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL", "http://minio:9000")
    OTEL_EXPORTER_OTLP_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    API_TITLE = "Allotment Planner API"
    API_VERSION = "v1"
    OPENAPI_VERSION = "3.0.3"
    OPENAPI_URL_PREFIX = "/api"
    OPENAPI_JSON_PATH = "openapi.json"
    OPENAPI_SWAGGER_UI_PATH = "docs"
    OPENAPI_SWAGGER_UI_URL = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    OTEL_EXPORTER_OTLP_ENDPOINT = None
