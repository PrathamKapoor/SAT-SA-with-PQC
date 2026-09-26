"""Durable artifact storage contract shared by local and object backends."""

from __future__ import annotations

import io

import pytest

from qsmlops.crypto.hashing import sha3_hex


def test_local_store_is_immutable_and_blocks_traversal(tmp_path):
    from satsa.submissions import LocalArtifactStorage

    store = LocalArtifactStorage(tmp_path / "artifacts")
    source = tmp_path / "source"
    source.write_bytes(b"trusted bytes")
    digest = sha3_hex(b"trusted bytes")
    key = f"org-a/version-a/alerts/{digest}.csv"
    store.put_file(source, key, "text/csv", digest)
    store.put_file(source, key, "text/csv", digest)
    dest = tmp_path / "copy"
    store.copy_to(key, dest)
    assert dest.read_bytes() == b"trusted bytes"

    source.write_bytes(b"different bytes")
    with pytest.raises((ValueError, FileExistsError)):
        store.put_file(source, key, "text/csv", sha3_hex(b"different bytes"))
    for bad_key in ("../escape", "/absolute", "org-a/../../escape", "org-a\\escape"):
        with pytest.raises(ValueError):
            store.put_file(source, bad_key, "text/csv", sha3_hex(b"different bytes"))


def test_s3_adapter_uses_streamed_body_and_server_digest(tmp_path):
    from satsa.submissions import S3ArtifactStorage

    class Client:
        def __init__(self):
            self.objects = {}
            self.last_put = None

        def put_object(self, **kwargs):
            assert kwargs["IfNoneMatch"] == "*"
            assert kwargs["ContentLength"] == 5
            self.last_put = kwargs
            self.objects[kwargs["Key"]] = kwargs["Body"].read()

        def get_object(self, **kwargs):
            return {"Body": io.BytesIO(self.objects[kwargs["Key"]])}

        def head_object(self, **kwargs):
            body = self.objects[kwargs["Key"]]
            return {"ContentLength": len(body), "Metadata": self.last_put["Metadata"]}

    client = Client()
    store = S3ArtifactStorage(bucket="test-bucket", prefix="sat-sa", client=client)
    source = tmp_path / "source"
    source.write_bytes(b"hello")
    digest = sha3_hex(b"hello")
    store.put_file(source, "org-a/version-a/alerts/data.csv", "text/csv", digest)
    store.verify_object("org-a/version-a/alerts/data.csv", digest=digest, size=5)
    dest = tmp_path / "copy"
    store.copy_to("org-a/version-a/alerts/data.csv", dest)
    assert dest.read_bytes() == b"hello"
    assert client.last_put["Metadata"] == {"sha3-256": digest}
