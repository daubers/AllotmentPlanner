"""The frontend's generated client is built from frontend/openapi.json; keep it in sync."""

import json
from pathlib import Path

import pytest

SPEC = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"


def _normalise(spec: dict) -> dict:
    """Python 3.13 renamed HTTP 422 to UNPROCESSABLE_CONTENT (was UNPROCESSABLE_ENTITY), and
    flask-smorest uses that name for a response component. Ignore the rename so the check
    gives the same answer on any supported Python."""
    text = json.dumps(spec, sort_keys=True)
    return json.loads(text.replace("UNPROCESSABLE_ENTITY", "UNPROCESSABLE_CONTENT"))


@pytest.mark.skipif(not SPEC.exists(), reason="frontend/ is not available (e.g. in the api image)")
def test_committed_openapi_matches_the_api(client):
    live = client.get("/api/openapi.json").json
    assert _normalise(json.loads(SPEC.read_text())) == _normalise(live), (
        "frontend/openapi.json is stale. Run: docker compose exec -T api flask openapi print "
        "> frontend/openapi.json && (cd frontend && npm run gen:api)"
    )
