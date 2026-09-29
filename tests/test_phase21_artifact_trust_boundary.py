"""Phase 21Y: executable model formats never deserialize untrusted bytes."""

import hashlib
import pickle

import pytest

from qsmlops.ml.adapters import (
    SKLearnSerializer,
    UntrustedArtifactError,
    verified_artifact_bytes,
)


class _Exploit:
    def __reduce__(self):  # would run on unpickling
        return (pytest.fail, ("untrusted pickle was executed",))


def test_pickle_without_trusted_digest_is_refused():
    payload = pickle.dumps(_Exploit())
    with pytest.raises(UntrustedArtifactError):
        SKLearnSerializer().deserialize(payload)


def test_pickle_with_wrong_digest_is_refused():
    payload = pickle.dumps(_Exploit())
    with pytest.raises(UntrustedArtifactError):
        SKLearnSerializer().deserialize(payload, expected_digest="0" * 64)


def test_bytes_matching_the_trusted_digest_load():
    payload = pickle.dumps({"weights": [1, 2]})
    digest = hashlib.sha3_256(payload).hexdigest()
    assert SKLearnSerializer().deserialize(payload, expected_digest=digest) == {"weights": [1, 2]}
    assert verified_artifact_bytes(payload, digest) == payload
