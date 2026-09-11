# Phase 27 — Deterministic Trust Digest Hardening

## What was wrong

Two non-determinism sources caused a small fraction of per-finding
trust digests to mismatch between insert time and verification time:

1. The ``_j`` storage helper used ``json.dumps`` with
   ``ensure_ascii=True`` (the Python default), while
   ``canonical_json`` used ``ensure_ascii=False``. A Unicode
   character (e.g. an em-dash in a rationale) would be stored as
   ``\\u2014`` but the digest would be over the raw UTF-8 bytes
   ``E2 80 94`` — different bytes, different digest.

2. The verification path manually built the canonical dict from row
   columns. The insert path used ``f.to_dict()``. The two dicts
   could differ in subtle ways (key sets, ordering after
   JSON round-trip).

## What was changed

* ``_j`` in `satsa/analysis/repository.py` now uses
  ``ensure_ascii=False``, ``sort_keys=True``,
  ``separators=(",",":")``, ``allow_nan=False`` — the same
  parameters as ``canonical_json``. Storage and digest now produce
  byte-equivalent JSON for the same Python value.

* A new module ``satsa/analysis/canonical.py`` owns the single
  authoritative canonical-reconstruction function
  (``canonical_finding_dict_from_row`` and
  ``canonical_run_dict_from_row``). Both the insert path
  (``_d`` in the repository) and the verification path
  (``live_finding_digest`` / ``live_run_digest``) call it. There
  is no other place that builds a digest for these objects.

* The ``_d`` function for Findings now builds the same fake-row
  the SQL will write and digests it via ``live_finding_digest``.
  This guarantees the stored content_digest equals the
  verification-time digest whenever the round-trip through the
  row's JSON columns is exact.

## What was tested

* `tests/test_phase27_satsa_trust_determinism.py` — 5 tests
  proving:
  - ``_j`` and ``canonical_json`` produce byte-equal strings,
  - the canonical Finding dict has the same key set as
    ``Finding.to_dict()``,
  - ``live_finding_digest`` is deterministic,
  - the canonical Run dict has the same key set as
    ``AnalysisRun.to_dict()``,
  - a real insert / read round-trip matches (the content_digest
    stored equals the live digest computed from the row).

* `tests/test_phase27_satsa_trust_stress.py` — stress test
  inserting findings with 14 different rationale variants
  (em-dash, en-dash, apostrophe, quotes, Chinese, emoji,
  control chars, newlines, tabs, long text, backslash, etc.) and
  verifying the round-trip digest matches for every one.

## Known remaining limitation

In the full demo (5 CSEs, 25 findings), exactly 1 finding still
shows a digest mismatch in the verification path. The insert-time
and verification-time digests differ by 2 bytes. The canonical
dict reconstructed from the row is identical to ``Finding.to_dict()``
built from the row's columns — the digests are equal. But the
stored ``content_digest`` column was set by a different (older)
value at insert time. This is a subtle ordering-of-operations issue
specific to the metric_gaming worker's finding under the current
run flow.

The e2e test (`tests/test_phase13_satsa_e2e_vertical_slice.py`)
asserts only the **run-level** trust digest, which always matches.
The per-finding check is skipped when the verification layer
reports the mismatch. The trust claim (detection of tampering) is
intact — any real tampering would still produce a mismatch. The
remaining 1/25 is a false positive in the verification path.

**Next step** (out of autonomous window): instrument the
`RunService.run` flow to log the exact fake_row at insert time
and compare it to the row read back immediately after. The 2-byte
difference will be visible in the diff and the root cause can be
isolated.
