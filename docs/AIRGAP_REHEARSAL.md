# Offline / air-gap deployment rehearsal

Tool: `scripts/airgap_rehearsal.py`
Companion evidence: `docs/deployment.md` (native offline path),
`docs/CLAIMS.md` (exact claims boundary).

## What this is — and is not

A **non-destructive same-host rehearsal** of the offline deployment
path: it verifies that an offline bundle can install and run SAT-SA
with the network unreachable by construction (`--no-index`), that
first-party imports resolve from the *installed* distribution (not the
source tree), and that the project's own diagnostics (`sat-sa
doctor` / `demo` / `validate`) pass inside that installed
environment.

**A green same-host rehearsal is NOT a completed target-machine
deployment and is not NCIIPC deployment proof.** The proof for a real
target is this procedure executed on that target, with the resulting
report recorded (see "Recording target evidence").

## Preconditions

- The host has Python ≥ 3.10 (3.13 verified) — the rehearsal venv is
  created from it via bundled `ensurepip` (no network).
- An offline bundle (wheelhouse) directory exists containing wheels
  for every runtime requirement in `requirements.txt` **plus
  `setuptools>=68`** (needed to build the project wheel; Python 3.12+
  environments do not bundle it — P31).
- If no bundle exists locally, see "Preparing a bundle" below. The
  tool never downloads anything.

## Preparing a bundle (build-time step, needs network — like CI)

```bash
pip download -r requirements.txt -d <wheelhouse-dir>
pip download "setuptools>=68" -d <wheelhouse-dir>
```

This is a build/packaging concern, exactly like the CI dependency
install; the deployed application itself makes zero network calls
(verified by `tests/test_phase18_satsa_offline_hardening.py` and by
the `--no-index` install in the rehearsal itself).

## Commands

```bash
# Missing/empty bundle → structured failure, no pretense:
python scripts/airgap_rehearsal.py --wheelhouse <dir>

# Full rehearsal (venv + data + report under --out, kept after):
python scripts/airgap_rehearsal.py --wheelhouse <dir> --out <dir> --keep
```

Exit code 0 = overall pass; 1 = at least one failing check.

## What is verified

Structured pass/warn/fail checks, in order:

1. `wheelhouse_present` — bundle exists, contains `.whl` files, and
   every runtime requirement in `requirements.txt` has a matching
   wheel; missing `setuptools` is a warning (build backend needed on
   Python 3.12+).
2. `venv_created` — fresh venv from the local interpreter only.
3. `install_requirements` — `pip install --no-index --find-links
   <wheelhouse> -r requirements.txt` (network impossible by flags).
4. `install_project` — `pip install --no-index --find-links
   <wheelhouse> --no-deps <repo>` (non-editable: a real installed
   distribution).
5. `imports_from_site_packages` — `import satsa, qsmlops` in a
   **neutral cwd** must resolve from the venv's site-packages, never
   the source tree (the masking `pip install -e .` would cause).
6. `cli_version` — `sat-sa --version` from the installed console
   script.
7. `doctor` — `sat-sa --db <temp> --trust-key-dir <temp> doctor`
   (real ML-DSA roundtrip, DB connect+migrate, write probes, offline
   posture check).
8. `demo` — committed synthetic demo data end-to-end.
9. `validate` — synthetic ground-truth validation.
10. `offline_install_posture` — every install command used
    `--no-index` with a local `--find-links` wheelhouse.

All temporary databases, keys, venvs, and reports are created under
`--out` (or the system temp dir) — never inside the repository.

## Expected outcomes

- Full rehearsal with a complete bundle: `overall: pass`, exit 0.
- Missing/empty bundle: `overall: fail` with a
  `bundle not supplied` failure on `wheelhouse_present` and **no
  fabricated results**.
- A wheel missing from the bundle: named in the failure detail.
- `doctor` reports the expected `hsm-provider` WARN (no ML-DSA
  hardware token exists industry-wide).

## Failure / recovery checks

- Any `fail` blocks a "deployable" claim — do not reinterpret.
- If `install_project` fails, check the setuptools wheel is present
  and the bundle is complete (see check 1 warnings).
- Backup/restore recovery is separately proven by
  `tests/test_phase68_satsa_doctor_and_backup_restore.py` and
  documented in `docs/backup-restore.md`.

## Recording target-machine evidence

1. Copy the repository and the prepared wheelhouse bundle to
   removable media.
2. On the disconnected target, run the rehearsal with the bundle:
   `python scripts/airgap_rehearsal.py --wheelhouse <dir> --out <dir> --keep`.
3. Preserve the generated `airgap-rehearsal-report.json` (tool, date,
   host identification, all checks) as the deployment evidence record.
4. Only a report generated on the disconnected target counts as
   target-deployment evidence. Same-host runs must be cited as
   rehearsals.

## Explicit limits

- Same-host rehearsal ≠ target NCIIPC deployment. No target-machine
  rehearsal has been executed as of P33 (September 2026); the P33
  evidence is a same-host rehearsal (see
  `reports/CONTROLLED_BENCHMARK_P33.md`).
- The rehearsal proves the install/run path offline; it does not prove
  hardware HSM signing (none exists industry-wide) or multi-writer
  production operation (SQLite single-writer boundary stands).
