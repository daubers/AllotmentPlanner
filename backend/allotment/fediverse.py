"""A small Mastodon API client: verify a token, upload media, post a status.

Instance URLs come from users, so the server will fetch whatever they type. We therefore
require https, refuse redirects and refuse loopback/private addresses unless
``FEDIVERSE_ALLOW_PRIVATE_HOSTS`` is set (local development against a test instance).
"""

import ipaddress
import socket
import time
from urllib.parse import urlsplit

import requests
from flask import current_app

TIMEOUT = 15
MAX_STATUS_CHARS = 480  # Mastodon's default limit is 500; leave room
VISIBILITIES = ("public", "unlisted", "private", "direct")


class MastodonError(Exception):
    """``permanent`` errors won't be fixed by retrying (bad token, rejected content)."""

    def __init__(self, message: str, permanent: bool = False):
        super().__init__(message)
        self.permanent = permanent


def _allow_private() -> bool:
    return bool(current_app.config.get("FEDIVERSE_ALLOW_PRIVATE_HOSTS"))


def normalise_instance_url(raw: str) -> str:
    """'Mastodon.Social/' -> 'https://mastodon.social'. Raises ValueError with a user message."""
    text = (raw or "").strip()
    if not text:
        raise ValueError("Enter your instance, e.g. mastodon.social")
    if "://" not in text:
        text = f"https://{text}"
    parts = urlsplit(text)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("Instance must be a web address like https://mastodon.social")
    if parts.username or parts.password:
        raise ValueError("Don't put a username or password in the instance address")
    if parts.path not in ("", "/") or parts.query or parts.fragment:
        raise ValueError("Use just the instance address, without a path")
    if parts.scheme == "http" and not _allow_private():
        raise ValueError("The instance must use https")
    host = parts.hostname.lower()
    netloc = f"{host}:{parts.port}" if parts.port else host
    if ":" in host:  # IPv6 literal
        netloc = f"[{host}]" + (f":{parts.port}" if parts.port else "")
    return f"{parts.scheme}://{netloc}"


def _is_blocked(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%")[0])
    return not ip.is_global or ip.is_multicast


def ensure_public_host(base_url: str) -> None:
    """Refuse hosts that resolve to private/loopback addresses (SSRF guard)."""
    if _allow_private():
        return
    host = urlsplit(base_url).hostname or ""
    try:
        addresses = (
            [host]
            if _is_ip(host)
            else [info[4][0] for info in socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)]
        )
    except socket.gaierror as exc:
        raise MastodonError(f"Couldn't find {host}: check the instance name") from exc
    if any(_is_blocked(a) for a in addresses):
        raise MastodonError("That address points at a private network and isn't allowed", True)


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


class MastodonClient:
    def __init__(self, base_url: str, token: str, media_poll_seconds: float = 1.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.media_poll_seconds = media_poll_seconds

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        ensure_public_host(self.base_url)
        headers = {"Authorization": f"Bearer {self.token}", **kwargs.pop("headers", {})}
        try:
            resp = requests.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                timeout=TIMEOUT,
                allow_redirects=False,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise MastodonError(f"Couldn't reach the instance ({exc.__class__.__name__})") from exc
        if 300 <= resp.status_code < 400:
            raise MastodonError("The instance redirected the request; check its address", True)
        if resp.status_code in (401, 403):
            raise MastodonError("The instance rejected the access token", True)
        if resp.status_code == 429 or resp.status_code >= 500:
            raise MastodonError(f"The instance is busy or down (HTTP {resp.status_code})")
        if resp.status_code >= 400:
            raise MastodonError(f"Rejected by the instance: {_error_text(resp)}", True)
        return resp

    def verify_credentials(self) -> str:
        """Returns the account handle, e.g. 'plot@mastodon.social'."""
        acct = self._request("GET", "/api/v1/accounts/verify_credentials").json().get("acct", "")
        host = urlsplit(self.base_url).hostname
        return acct if "@" in acct else f"{acct}@{host}"

    def upload_media(self, path: str, filename: str, content_type: str, description: str) -> str:
        with open(path, "rb") as f:
            resp = self._request(
                "POST",
                "/api/v2/media",
                files={"file": (filename, f, content_type)},
                data={"description": description[:1400]} if description else None,
            )
        media_id = resp.json()["id"]
        if resp.status_code == 202:  # still being processed: wait until it can be attached
            for _ in range(30):
                time.sleep(self.media_poll_seconds)
                if self._request("GET", f"/api/v1/media/{media_id}").status_code == 200:
                    break
            else:
                raise MastodonError("The instance took too long to process the photo")
        return media_id

    def create_status(
        self, text: str, visibility: str, media_ids: list[str], idempotency_key: str
    ) -> dict:
        body: dict = {"status": truncate(text), "visibility": visibility}
        if media_ids:
            body["media_ids[]"] = media_ids
        resp = self._request(
            "POST", "/api/v1/statuses", data=body, headers={"Idempotency-Key": idempotency_key}
        )
        return resp.json()


def truncate(text: str, limit: int = MAX_STATUS_CHARS) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _error_text(resp: requests.Response) -> str:
    try:
        return str(resp.json().get("error") or resp.reason)[:200]
    except ValueError:
        return f"HTTP {resp.status_code}"
