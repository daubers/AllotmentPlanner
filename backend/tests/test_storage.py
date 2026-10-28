import boto3
import pytest
from moto import mock_aws

from allotment.storage import FileStorage, S3Storage

DATA = bytes(range(256)) * 40  # 10,240 bytes


@pytest.fixture(params=["file", "s3"])
def storage(request, tmp_path):
    if request.param == "file":
        yield FileStorage(str(tmp_path / "store"))
    else:
        with mock_aws():
            client = boto3.client("s3", region_name="us-east-1")
            yield S3Storage(client, "test-bucket")  # bucket is created on first put


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "src.bin"
    path.write_bytes(DATA)
    return str(path)


def test_roundtrip_size_and_ranges(storage, source, tmp_path):
    storage.put("a/b/file.bin", source, "application/octet-stream")
    assert storage.size("a/b/file.bin") == len(DATA)
    out = tmp_path / "out.bin"
    storage.download("a/b/file.bin", str(out))
    assert out.read_bytes() == DATA
    assert b"".join(storage.read_range("a/b/file.bin", 0, 9)) == DATA[:10]
    assert b"".join(storage.read_range("a/b/file.bin", 100, 5000)) == DATA[100:5001]
    assert b"".join(storage.read_range("a/b/file.bin", len(DATA) - 3, len(DATA) - 1)) == DATA[-3:]


def test_large_ranges_stream_in_chunks(storage, tmp_path):
    big = tmp_path / "big.bin"
    big.write_bytes(b"x" * (2 * 1024 * 1024 + 123))
    storage.put("big.bin", str(big), "application/octet-stream")
    chunks = list(storage.read_range("big.bin", 0, 2 * 1024 * 1024 + 122))
    assert len(chunks) > 1 and sum(map(len, chunks)) == 2 * 1024 * 1024 + 123


def test_delete(storage, source):
    storage.put("gone.bin", source, "application/octet-stream")
    storage.delete("gone.bin")
    with pytest.raises(Exception):  # noqa: B017 - FileNotFoundError or botocore ClientError
        storage.size("gone.bin")


def test_file_storage_rejects_path_traversal(tmp_path, source):
    store = FileStorage(str(tmp_path / "store"))
    with pytest.raises(ValueError):
        store.put("../escape.bin", source, "application/octet-stream")
    assert not (tmp_path / "escape.bin").exists()
