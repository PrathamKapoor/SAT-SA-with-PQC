# Evidence Packet Persistence — Workstream F1

**Status:** COMPLETE
**Date:** 2026-09-01
**Workstream:** F1 — Ledger Packet Payload Persistence (post-roadmap hardening)
**Authority:** DELIVERABLE.md “Verification Packets: Immutable evidence for every operation” + `qsmlops/evidence/packet.py` + `qsmlops/evidence/ledger.py` (EvidenceLedger is authoritative store) — gap was that ledger committed to digests but not to bodies. Classified as DOCUMENTED FUTURE in `POST_ROADMAP_ENGINEERING_AUDIT.md:129` (“out of scope”) and `POST_ROADMAP_HARDENING_IMPLEMENTATION.md:5`; now elevated to **AUTHORITATIVE hardening** because the ledger’s promise of “immutable evidence” is unrealizable without payload durability (auditor cannot reconstruct *why* a decision was VERIFIED/QUARANTINE).
**Environment:** No external infra required; uses existing `ArtifactStore` content-addressed primitives.

---

## 1. Why Persistence Exists

* **Before F1:** `EvidenceLedger.append_packet()` stored only `{type, packet_id, digest, objective, actor, decision}` (5 fields). The full `VerificationPacket` (`inputs`, `artifacts`, `metrics`, `security_checks`, `proofs`, `decision`, `status`) was ephemeral — only its SHA3 digest was committed. An auditor could see *that* a packet was VERIFIED, but not *which* 12 security checks or which crypto proofs justified it.
* **After F1:** Every `VerificationPacket` body is durably stored **content-addressed by its canonical SHA3-256 digest** under `<ledger_parent>/packets/<digest[:2]>/<digest>`. The ledger entry commits to `digest`; the body is retrievable and digest-verified. The ledger remains the ordering/chain authority; the packet store is the body authority. No duplication.

## 2. Authority / Source

| Source | Statement | Level |
|---|---|---|
| `qsmlops/evidence/packet.py:1` | “Quantum Verification Packet: immutable evidence for every important operation. Packets are hashed into the evidence ledger, making operational history tamper-evident.” | AUTHORITATIVE |
| `docs/ARCHITECTURE.md:68` | `evidence/ledger.py — append-only hash-chained ledger (authoritative store)` + `packet.py — VerificationPacket (tamper-evident decision records)` | AUTHORITATIVE |
| `DELIVERABLE.md:14` | “Verification Packets: Immutable evidence for every operation” | AUTHORITATIVE |
| `POST_ROADMAP_ENGINEERING_AUDIT.md:129` | “Evidence F1 (ledger packet payload not persisted): DOCUMENTED FUTURE — out of scope” | DEFERRED → now justified as integrity gap |
| `POST_ROADMAP_HARDENING_IMPLEMENTATION.md:5` | Gap table lists F1 as deferred | DEFERRED → now closed |

No new product roadmap item invented; this is a **hardening fix** for evidence completeness, analogous to S1–S5/C1–T8.

## 3. Architecture

```
VerificationPacket.create(...)
        ↓
  canonical_json(packet.to_dict())  — qsmlops.crypto.hashing.canonical_json (sorted keys, compact)
        ↓
  sha3_hex(canonical)  →  digest  — packet.digest()
        ↓
  ArtifactStore.put(canonical)  →  <home>/ledger/packets/<digest[:2]>/<digest>
        ↓ (content-addressed, idempotent, atomic via tempfile)
  EvidenceLedger.append({type:"verification_packet", packet_id, digest, objective, actor, decision})
        ↓
  hash-chain entry_hash = sha3_hex({seq, timestamp, prev_hash, record})
        ↓
  ledger.jsonl (append-only) + packets/ (content-addressed)

Retrieval:
  ledger.find_by_packet(packet_id) → digest → packet_store.get_if_exists(digest) → canonical → VerificationPacket.from_dict → digest-verified

Design choice: **content-addressed via ArtifactStore**, not embedded huge payload in every ledger row. Preserves:
  - hash-chaining (ledger record is tiny, deterministic)
  - tamper evidence (both ledger entry_hash and packet digest)
  - immutability (packet_id unique, digest binding)
  - auditability (body retrievable)
  - deterministic serialization (canonical_json)
  - no duplication (ArtifactStore already provides the primitive)
```

*No new PacketStore class* — reuses `ArtifactStore`. No second ledger.

## 4. Packet Lifecycle

1. **Verification** (`registry.verify_version`, `registry.approve_deployment`, `registry.deploy`, `supervisor.reason`, `pipeline.selfheal.evaluate_version`) creates `VerificationPacket` with `inputs, artifacts, metrics, security_checks, proofs, decision`.
2. **Persistence** (`EvidenceLedger.append_packet`):
   1. Sensitive check (`_contains_sensitive` scans for `private_key`, `secret_key`, `hsm_pin`, `pin`, `passphrase`, `credential` — fail-closed if found).
   2. Immutability: same `packet_id` → `LedgerError` (whether digest matches or not).
   3. Store body: `packet_store.put(canonical)`; assert stored digest == `packet.digest()`.
   4. Append ledger entry committing to `digest`.
3. **Retrieval** (`get_packet`, `get_packet_by_digest`, `verify_packet`, `list_packet_ids`).
4. **Audit** (`verify_chain` + `verify_packet`).

## 5. Storage Model

* **Ledger:** `<home>/ledger/evidence.jsonl` — JSONL, one entry per line, fields `seq, timestamp, prev_hash, record, entry_hash`. `record` for packets is `{type, packet_id, digest, objective, actor, decision}` (6 fields, ~200 bytes).
* **Packet store:** `<home>/ledger/packets/<digest[:2]>/<digest>` — raw canonical JSON bytes (typically 2–8 KB per packet, pretty-compact). Content-addressed, immutable, idempotent.
* **Config:** `PlatformConfig.packet_store_path` and `Settings.packet_store_path` both `ledger_path.parent / "packets"`; `ensure_dirs()` creates it.

## 6. Integrity Model

* **Ledger chain:** `verify_chain()` checks `prev_hash` linkage, `seq` continuity, `entry_hash = sha3_hex({seq, timestamp, prev_hash, record})`. Malformed lines reported as `corrupted ledger line`, not masked.
* **Packet digest binding:** `packet.digest() = sha3_hex(canonical_json(packet.to_dict()))`. Ledger `record.digest` must equal packet digest; `get_packet` verifies `packet.digest() == digest` on load, otherwise `None` (tampered).
* **Packet immutability:** `packet_id` is UUID4 hex, unique; second `append_packet` with same `packet_id` → `LedgerError` (whether digest same or different).
* **Tamper detection:** If packet file is overwritten or truncated, `get_if_exists` raises `IOError` (digest mismatch) or `get_packet` returns `None`; `verify_packet` returns `(False, "packet body digest mismatch (tampered)")`.

## 7. Security Model

| Field | Class | Persisted? |
|---|---|---|
| `packet_id`, `objective`, `actor`, `decision`, `status`, `inputs`, `artifacts`, `metrics`, `security_checks`, `proofs` (suite_id, signer_key_id, signed_digest, signature_verified, artifact_integrity) | PUBLIC / INTERNAL | Yes |
| `proofs.crypto` contains only public suite/key ids and digests | PUBLIC | Yes |
| `private_key`, `secret_key`, `hsm_pin`, `pin`, `passphrase`, `credential` | SECRET | **Never** — `_contains_sensitive` rejects packet if any such field name appears (case-insensitive, exact for `pin`). No HSM PINs, passphrases, tokens, private keys are ever constructed in packets (verified by code inspection: `packet.py`, `registry.py`, `supervisor.py` never populate them). |

*Error messages scrub PINs; `verify_packet` distinguishes “missing” vs “tampered” without leaking content.*

## 8. Backward Compatibility

* Old ledger files (pre-F1) with `verification_packet` entries and **no** packet body still `verify_chain() == True`. `get_packet` returns `None`, `verify_packet` returns `(False, "packet body missing… (malformed digest)"` for placeholder digests like `"abc"`, or `(False, "packet body missing…")` for valid-form digests whose file is absent. No crash.
* Existing `EvidenceLedger(path)` constructor remains compatible (second arg `packet_store_path` optional, defaults to `path.parent / "packets"`).
* Ledger hash-chain semantics unchanged (record is still the 6-field packet reference).

## 9. Failure Handling

| Failure | Behavior |
|---|---|
| Packet contains sensitive field | `LedgerError: sensitive field 'x' ; persistence rejected` — fail-closed, no ledger entry |
| Duplicate `packet_id` | `LedgerError: packet_id … already exists (immutable)` |
| Packet store unavailable (disk full, permission) | `LedgerError: packet store unavailable` — no ledger entry committed (store before ledger) |
| Digest mismatch on store (`put` returns different digest) | `LedgerError: digest mismatch` |
| Ledger append after store succeeds | Store orphan (content-addressed) remains; no false claim. GC-able. |
| Packet file deleted/corrupted | `get_packet` → `None`, `verify_packet` → `(False, "missing"/"tampered")` |
| Malformed packet JSON | `get_packet_by_digest` → `None` |
| Duplicate `packet_id` with different digest | `LedgerError` (immutable) |
| Concurrent appends | `Ledger._lock` protects `find_by_packet` check + `packet_store.put` is atomic (tempfile) |

No silent success when persistence failed.

## 10. API / CLI Impact

* **API** (`qsmlops/api/app.py:387`):
  * `GET /evidence/packet/{packet_id}` — 200 with packet JSON, 404 if not found / missing / tampered (never 500). Digest-verified.
  * `GET /evidence/packet/by-digest/{digest}` — 200 / 404.
  * `GET /evidence/packets` — list committed packet_ids.
* **CLI** (`qsmlops/cli.py:305`):
  * `show-packet --packet-id ID` — prints packet JSON or error to stderr (exit 1).
  * `audit-ledger-packets` — verifies every ledger-committed packet body (`total_packets`, `failures`, `all_intact`).
  * `audit-ledger` unchanged (chain only).
* Both surfaces are **read-only**, no mutation, no secret exposure, 404 for illegal state.

## 11. Tests

`tests/test_evidence_packet_persistence.py` — **32 tests**:

* **Persistence (6):** persisted, survives restart, by-digest, digest matches, immutable, duplicate idempotent
* **Integrity (6):** modified rejected, mismatched digest, missing, corrupted, malformed id, historical without packet
* **Ledger (4):** chain valid, reference committed, historical valid, list ids
* **Security (5):** secrets, private_key, passphrase, nested, normal passes
* **Compatibility (2):** old ledger loads, demo works
* **Integration (2):** verification→ledger→retrieval, registry uses persisted packets
* **Adversarial (7):** mutation after persistence, digest substitution, deletion, truncated, wrong model binding, wrong signer, concurrent appends

All 32 green; partitioned regression 368 green.

## 12. Limitations

* Packet store is local filesystem (`ArtifactStore` under `ledger/packets`), single-host, no retention/GC, no replication — consistent with existing ledger/packet tier-3 store.
* Porting packets to PostgreSQL/object-store would require explicit owner decision (not needed for F1).
* No encryption at rest for packet bodies (they contain only public evidence; secrets are rejected).

## 13. Migration

* **No migration required.** Old ledger entries remain valid; new `append_packet` calls automatically store bodies. Old entries' packet bodies are simply absent (treated as missing, not error). If historical packet bodies are desired, they would need to be re-derived from `inputs`/`artifacts`/`metrics` (not attempted).

## 14. Reproduction Commands

```bash
python -m compileall -q qsmlops && echo OK
python demo.py  # Chain OK: True, packets under ledger/packets/
python -m pytest tests/test_evidence_packet_persistence.py -q  # 32 passed
python -m pytest tests/test_post_roadmap_hardening.py tests/test_hsm* -q  # 94 passed
# API
pip install httpx && python -c "from fastapi.testclient import TestClient; from qsmlops.api.app import register_dashboard_routes; ..."
# CLI
qsmlops --home ~/.qsmlops audit-ledger
qsmlops --home ~/.qsmlops audit-ledger-packets
qsmlops --home ~/.qsmlops show-packet --packet-id <uuid>
python -c "from qsmlops.config import PlatformConfig; from qsmlops.evidence.ledger import EvidenceLedger; from pathlib import Path; print(EvidenceLedger(PlatformConfig(Path.home()/'.qsmlops').ledger_path).verify_chain())"
```

