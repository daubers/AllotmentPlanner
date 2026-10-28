from allotment.config import Config


def test_limits_report_the_upload_ceiling(client, register, app):
    headers, _ = register()
    resp = client.get("/api/v1/limits", headers=headers)
    assert resp.status_code == 200
    assert resp.json == {"max_upload_bytes": app.config["MAX_CONTENT_LENGTH"]}


def test_limits_need_a_login(client):
    assert client.get("/api/v1/limits").status_code == 401


def test_default_limit_fits_a_gopro_chapter():
    # GoPro splits recordings into chapters of at most about 4 GB.
    assert Config.MAX_CONTENT_LENGTH >= 4 * 1000**3
