import pytest
from argon2 import PasswordHasher
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


@pytest.fixture(scope="session", autouse=True)
def _cheap_password_hashing():
    """argon2's defaults are deliberately slow (about 35 ms a user, and most tests register
    several); the tests only need the hash and verify round trip. Parameters are stored in each
    hash, so verifying still works."""
    from allotment import security

    original = security._hasher
    security._hasher = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
    yield
    security._hasher = original


@pytest.fixture(scope="session")
def _schema(_test_database):
    """Build the tables once for the whole run (create and drop per test cost about 0.8 s)."""
    app = create_app(TestConfig)
    with app.app_context():
        db.drop_all()  # whatever an interrupted run left behind
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


@pytest.fixture
def media_root(tmp_path):
    return tmp_path / "media"


@pytest.fixture
def app(media_root, _schema):
    class Config(TestConfig):
        MEDIA_ROOT = str(media_root)

    app = create_app(Config)
    with app.app_context():
        # Empty every table and restart the ids, rather than rebuilding the schema. DELETE and
        # setval take about 30 ms; TRUNCATE rewrites and syncs every table's files, which is
        # slower than rebuilding. Done before the test, so a run that was killed half way cannot
        # leak rows into the next.
        db.session.rollback()
        tables = db.metadata.sorted_tables
        for table in reversed(tables):  # children before the tables they point at
            db.session.execute(text(f'DELETE FROM "{table.name}"'))
        for table in tables:
            db.session.execute(
                text(
                    "SELECT setval(seq, 1, false) FROM "
                    "(SELECT pg_get_serial_sequence(:t, 'id') AS seq) s WHERE seq IS NOT NULL"
                ),
                {"t": f'"{table.name}"'},
            )
        db.session.commit()
        yield app
        db.session.remove()


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
