"""S3 adapter exercised against a real HTTP S3-compatible test service."""

import hashlib
import socket

import pytest

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError
    from moto.server import ThreadedMotoServer
except ImportError:
    pytest.skip("install the s3-test optional dependencies", allow_module_level=True)


def test_s3_storage_http_upload_read_digest_and_cleanup(tmp_path):
    from satsa.submissions.storage import S3ArtifactStorage, file_sha3_256

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = ThreadedMotoServer(ip_address="127.0.0.1", port=port, verbose=False)
    server.start()
    host, port = server.get_host_and_port()
    client = boto3.client(
        "s3",
        endpoint_url=f"http://{host}:{port}",
        aws_access_key_id="phase6-test-only",
        aws_secret_access_key="phase6-test-only",
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
    )
    bucket = "satsa-phase6-integration"
    try:
        client.create_bucket(Bucket=bucket)
        content = b"id,severity\nA-1,high\n"
        source = tmp_path / "upload.csv"
        source.write_bytes(content)
        digest = hashlib.sha3_256(content).hexdigest()
        storage = S3ArtifactStorage(bucket=bucket, prefix="tenant", client=client)
        storage.put_file(source, "org/version/alerts.csv", "text/csv", digest)
        target = tmp_path / "download.csv"
        storage.copy_to("org/version/alerts.csv", target)
        assert target.read_bytes() == content
        assert file_sha3_256(target) == digest
        assert (
            client.head_object(Bucket=bucket, Key="tenant/org/version/alerts.csv")[
                "Metadata"
            ]["sha3-256"]
            == digest
        )
        changed = tmp_path / "different.csv"
        changed.write_bytes(b"different")
        with pytest.raises(FileExistsError):
            storage.put_file(
                changed, "org/version/alerts.csv", "text/csv", file_sha3_256(changed)
            )
        # Clean only the test object. Production submissions remain immutable;
        # object lifecycle/retention belongs to the configured bucket policy.
        client.delete_object(Bucket=bucket, Key="tenant/org/version/alerts.csv")
        with pytest.raises(ClientError) as missing:
            storage.copy_to("org/version/alerts.csv", target)
        assert missing.value.response["Error"]["Code"] in {"NoSuchKey", "404"}
    finally:
        server.stop()
