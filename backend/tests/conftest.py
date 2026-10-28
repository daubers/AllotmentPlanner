import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from allotment import create_app
from allotment.config import TestConfig
from allotment.extensions import db


@pytest.fixture(scope="session", autouse=True)
def _test_database():
    """Create the PostGIS test database on first use (it is separate from the dev database)."""
    url = make_url(TestConfig.SQLALCHEMY_DATABASE_URI)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url.database}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()
    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    engine.dispose()


@pytest.fixture
def media_root(tmp_path):
    return tmp_path / "media"


@pytest.fixture
def app(media_root):
    class Config(TestConfig):
        MEDIA_ROOT = str(media_root)

    app = create_app(Config)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def register(client):
    """Register a user and return (headers, user_json)."""

    def _register(email="a@example.com", name="Alex", password="password123"):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": email, "display_name": name, "password": password},
        )
        assert resp.status_code == 201, resp.json
        return {"Authorization": f"Bearer {resp.json['access_token']}"}, resp.json["user"]

    return _register
