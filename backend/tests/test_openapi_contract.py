"""The frontend's generated client is built from frontend/openapi.json; keep it in sync."""

import json
from pathlib import Path

import pytest

SPEC = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"


@pytest.mark.skipif(not SPEC.exists(), reason="frontend/ is not available (e.g. inside the api image)")
def test_committed_openapi_matches_the_api(client):
    live = client.get("/api/openapi.json").json
    assert json.loads(SPEC.read_text()) == live, (
        "frontend/openapi.json is stale. Run: docker compose exec -T api flask openapi print "
        "> frontend/openapi.json && (cd frontend && npm run gen:api)"
    )
