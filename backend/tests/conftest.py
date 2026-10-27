import pytest

from allotment import create_app
from allotment.config import TestConfig
from allotment.extensions import db


@pytest.fixture
def app():
    app = create_app(TestConfig)
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
