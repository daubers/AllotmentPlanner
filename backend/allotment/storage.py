"""Object storage for uploaded media: plain files (default) or any S3-compatible service."""

import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

from flask import Flask, current_app

CHUNK = 1024 * 1024


class Storage(Protocol):
    def put(self, key: str, path: str, content_type: str) -> None: ...
    def download(self, key: str, path: str) -> None: ...
    def size(self, key: str) -> int: ...
    def read_range(self, key: str, start: int, end: int) -> Iterator[bytes]:
        """Yield bytes ``start..end`` inclusive."""
        ...

    def delete(self, key: str) -> None: ...


class FileStorage:
    def __init__(self, root: str):
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError("Invalid storage key")
        return path

    def put(self, key: str, path: str, content_type: str) -> None:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)

    def download(self, key: str, path: str) -> None:
        shutil.copyfile(self._path(key), path)

    def size(self, key: str) -> int:
        return self._path(key).stat().st_size

    def read_range(self, key: str, start: int, end: int) -> Iterator[bytes]:
        with open(self._path(key), "rb") as f:
            f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = f.read(min(CHUNK, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class S3Storage:
    def __init__(self, client, bucket: str):
        self.client = client
        self.bucket = bucket
        self._ready = False

    def _ensure_bucket(self) -> None:
        if self._ready:
            return
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except self.client.exceptions.ClientError:
            self.client.create_bucket(Bucket=self.bucket)
        self._ready = True

    def put(self, key: str, path: str, content_type: str) -> None:
        self._ensure_bucket()
        self.client.upload_file(path, self.bucket, key, ExtraArgs={"ContentType": content_type})

    def download(self, key: str, path: str) -> None:
        self.client.download_file(self.bucket, key, path)

    def size(self, key: str) -> int:
        return self.client.head_object(Bucket=self.bucket, Key=key)["ContentLength"]

    def read_range(self, key: str, start: int, end: int) -> Iterator[bytes]:
        body = self.client.get_object(Bucket=self.bucket, Key=key, Range=f"bytes={start}-{end}")[
            "Body"
        ]
        try:
            yield from body.iter_chunks(CHUNK)
        finally:
            body.close()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


def _build(app: Flask) -> Storage:
    cfg = app.config
    if cfg["STORAGE_BACKEND"] == "file":
        return FileStorage(cfg["MEDIA_ROOT"])
    import boto3

    client = boto3.client(
        "s3",
        endpoint_url=cfg["S3_ENDPOINT_URL"],
        aws_access_key_id=cfg["S3_ACCESS_KEY"],
        aws_secret_access_key=cfg["S3_SECRET_KEY"],
        region_name="us-east-1",
    )
    return S3Storage(client, cfg["S3_BUCKET"])


def get_storage() -> Storage:
    """The storage for the current app, created on first use."""
    app = current_app._get_current_object()
    if "storage" not in app.extensions:
        app.extensions["storage"] = _build(app)
    return app.extensions["storage"]


def safe_delete(*keys: str | None) -> None:
    """Remove objects, ignoring ones already gone: a leftover blob must not fail a request."""
    storage = get_storage()
    for key in keys:
        if key:
            try:
                storage.delete(key)
            except Exception:  # noqa: BLE001 - best effort, logged by caller context
                current_app.logger.warning("could not delete %s", key)
