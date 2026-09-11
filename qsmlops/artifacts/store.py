"""Content-addressed artifact store.

The store is the single source of truth for artifact bytes. An artifact's
SHA3-256 digest is its address: writes are idempotent and any byte-level
modification is immediately detectable because the content no longer matches
its claimed address.
"""
from __future__ import annotations

import tempfile
import os
from pathlib import Path

from qsmlops.crypto.hashing import sha3_hex


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def digest(data: bytes) -> str:
        return sha3_hex(data)

    def _path_for(self, digest_hex: str) -> Path:
        return self.root / digest_hex[:2] / digest_hex

    def put(self, data: bytes) -> str:
        digest = self.digest(data)
        path = self._path_for(digest)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(dir=str(path.parent))
            try:
                with os.fdopen(fd, "wb") as fh:
                    fh.write(data)
                os.replace(tmp_name, path)
            finally:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)
        return digest

    def get(self, digest_hex: str) -> bytes:
        data = self.get_if_exists(digest_hex)
        if data is None:
            raise KeyError(f"artifact {digest_hex} not found")
        return data

    def get_if_exists(self, digest_hex: str) -> bytes | None:
        self._validate_digest(digest_hex)
        path = self._path_for(digest_hex)
        if not path.exists():
            return None
        data = path.read_bytes()
        if self.digest(data) != digest_hex:
            raise IOError(f"artifact {digest_hex} corrupted on disk")
        return data

    def exists(self, digest_hex: str) -> bool:
        return self.get_if_exists(digest_hex) is not None

    def verify(self, digest_hex: str) -> bool:
        try:
            return self.get_if_exists(digest_hex) is not None
        except (IOError, ValueError):
            return False

    @staticmethod
    def _validate_digest(digest_hex: str) -> None:
        if len(digest_hex) != 64 or any(c not in "0123456789abcdef" for c in digest_hex):
            raise ValueError(f"malformed digest {digest_hex!r}")

    def delete(self, digest_hex: str) -> None:
        path = self._path_for(digest_hex)
        if path.exists():
            path.unlink()

    def iter_digests(self):
        for sub in sorted(self.root.iterdir()) if self.root.exists() else []:
            if sub.is_dir():
                for f in sorted(sub.iterdir()):
                    yield f.name
