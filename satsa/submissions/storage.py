"""Immutable file-backed and S3-compatible artifact storage adapters."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import Protocol

CHUNK_BYTES = 64 * 1024
_COMPONENT = re.compile(r"^[A-Za-z0-9._-]+$")


def validate_key(key: str) -> str:
    parts = key.split("/")
    if not key or any(
        part in {"", ".", ".."} or not _COMPONENT.fullmatch(part) for part in parts
    ):
        raise ValueError("invalid artifact storage key")
    return key


def file_sha3_256(path: Path) -> str:
    digest = hashlib.sha3_256()
    with Path(path).open("rb") as source:
        while chunk := source.read(CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


class ArtifactStorage(Protocol):
    def put_file(
        self, source: Path, key: str, content_type: str, digest: str
    ) -> None: ...
    def copy_to(self, key: str, destination: Path) -> None: ...
    def check_ready(self) -> None: ...
    def close(self) -> None: ...


class LocalArtifactStorage:
    """An immutable local volume; suitable for offline or durable mounted disks."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        validate_key(key)
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("artifact key escapes storage root")
        return path

    def put_file(self, source: Path, key: str, content_type: str, digest: str) -> None:
        if file_sha3_256(source) != digest:
            raise ValueError("artifact bytes do not match server digest")
        destination = self._path(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if file_sha3_256(destination) != digest:
                raise FileExistsError("artifact key already contains different bytes")
            return
        fd, temp_name = tempfile.mkstemp(prefix=".upload-", dir=destination.parent)
        try:
            with os.fdopen(fd, "wb") as output, Path(source).open("rb") as input_file:
                while chunk := input_file.read(CHUNK_BYTES):
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            try:
                os.link(temp_name, destination)
            except FileExistsError:
                if file_sha3_256(destination) != digest:
                    raise FileExistsError(
                        "artifact key already contains different bytes"
                    )
        finally:
            Path(temp_name).unlink(missing_ok=True)

    def check_ready(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.root.is_dir():
            raise OSError("artifact storage is unavailable")

    def close(self) -> None:
        return None

    def copy_to(self, key: str, destination: Path) -> None:
        source = self._path(key)
        if not source.is_file():
            raise FileNotFoundError(key)
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with source.open("rb") as input_file, destination.open("wb") as output:
                while chunk := input_file.read(CHUNK_BYTES):
                    output.write(chunk)
        except BaseException:
            destination.unlink(missing_ok=True)
            raise


class S3ArtifactStorage:
    """S3-compatible object backend; endpoint/credentials come from the caller."""

    def __init__(self, *, bucket: str, prefix: str = "", client=None) -> None:
        if not bucket:
            raise ValueError("S3 bucket is required")
        if prefix:
            validate_key(prefix.strip("/"))
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        if client is None:
            try:
                import boto3
            except ImportError as exc:
                raise RuntimeError("install the s3 optional dependencies") from exc
            client = boto3.client("s3")
        self.client = client

    def _key(self, key: str) -> str:
        validate_key(key)
        return f"{self.prefix}/{key}" if self.prefix else key

    def put_file(self, source: Path, key: str, content_type: str, digest: str) -> None:
        if file_sha3_256(source) != digest:
            raise ValueError("artifact bytes do not match server digest")
        object_key = self._key(key)
        try:
            with Path(source).open("rb") as body:
                self.client.put_object(
                    Bucket=self.bucket,
                    Key=object_key,
                    Body=body,
                    ContentLength=Path(source).stat().st_size,
                    ContentType=content_type,
                    Metadata={"sha3-256": digest},
                    IfNoneMatch="*",
                )
        except Exception as exc:
            response = getattr(exc, "response", {})
            code = str(response.get("Error", {}).get("Code", ""))
            if code not in {
                "PreconditionFailed",
                "ConditionalRequestConflict",
                "412",
                "409",
            }:
                raise
            existing = self.client.head_object(Bucket=self.bucket, Key=object_key)
            if existing.get("Metadata", {}).get("sha3-256") != digest:
                raise FileExistsError(
                    "artifact key already contains different bytes"
                ) from exc
        self.verify_object(key, digest=digest, size=Path(source).stat().st_size)

    def verify_object(
        self, key: str, *, digest: str | None = None, size: int | None = None
    ) -> None:
        result = self.client.head_object(Bucket=self.bucket, Key=self._key(key))
        if digest is not None and result.get("Metadata", {}).get("sha3-256") != digest:
            raise ValueError("stored artifact digest metadata mismatch")
        if size is not None and result.get("ContentLength") != size:
            raise ValueError("stored artifact size mismatch")

    def check_ready(self) -> None:
        self.client.head_bucket(Bucket=self.bucket)

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=self._key(key))

    def close(self) -> None:
        close = getattr(self.client, "close", None)
        if close is not None:
            close()

    def copy_to(self, key: str, destination: Path) -> None:
        response = self.client.get_object(Bucket=self.bucket, Key=self._key(key))
        body = response["Body"]
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with destination.open("wb") as output:
                while chunk := body.read(CHUNK_BYTES):
                    output.write(chunk)
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
        finally:
            if hasattr(body, "close"):
                body.close()
