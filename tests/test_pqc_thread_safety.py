"""The pure-Python ML-DSA/ML-KEM singletons are not thread-safe; providers serialize them.

Regression for concurrent supervisory finalization producing a receipt whose
signature did not verify (CI, Python 3.13).
"""

from __future__ import annotations

import sys
import threading

from qsmlops.crypto.providers import KEM_PROVIDERS, SIGNATURE_PROVIDERS


def _run_concurrently(work, threads: int = 3) -> None:
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)  # force frequent thread switches
    try:
        workers = [threading.Thread(target=work) for _ in range(threads)]
        for w in workers:
            w.start()
        for w in workers:
            w.join(timeout=120)
            assert not w.is_alive()
    finally:
        sys.setswitchinterval(previous)


def test_concurrent_ml_dsa_signatures_all_verify() -> None:
    provider = SIGNATURE_PROVIDERS["ML-DSA-65"]
    keypair = provider.generate_keypair()
    message = b"supervisory-finalization-digest"
    invalid: list[int] = []

    def work() -> None:
        for _ in range(6):
            signature = provider.sign(keypair.secret_key, message)
            if not provider.verify(keypair.public_key, message, signature):
                invalid.append(1)

    _run_concurrently(work)
    assert invalid == []


def test_concurrent_ml_kem_round_trips() -> None:
    provider = KEM_PROVIDERS["ML-KEM-768"]
    keypair = provider.generate_keypair()
    mismatched: list[int] = []

    def work() -> None:
        for _ in range(6):
            shared, ciphertext = provider.encapsulate(keypair.public_key)
            if provider.decapsulate(keypair.secret_key, ciphertext) != shared:
                mismatched.append(1)

    _run_concurrently(work)
    assert mismatched == []
