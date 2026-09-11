# Development Setup

## Requirements

- Python 3.10+ (project developed on 3.13)
- Core deps: `kyber-py`, `dilithium-py`, `cryptography`, `fastapi`, `uvicorn`,
  `pyyaml`, `click`, `numpy`, `scipy`, `httpx`
- Optional: `scikit-learn` (sklearn framework adapter), `torch`, `tensorflow`
- Dev: `pytest`

## Install

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # POSIX

pip install -e ".[dev]"
```

## Run the platform server

```bash
# development (default)
python -m qsmlops.app

# explicit environment + overrides
python -m qsmlops.app --env production --port 8080 --home C:\data\qsmlops
```

Foundation endpoints once running:

```
GET  /health          # liveness + ledger chain status
GET  /system/info     # version + settings summary
GET  /status          # audit/identity/model deployment summary
GET  /identity        # list identities
POST /identity        # create identity (kind: human|service|agent)
GET  /audit           # query audit events
GET  /audit/verify    # verify the evidence ledger chain
```

## Run the CLI

```bash
qsmlops init
qsmlops provision-dataset --name data --samples 200
qsmlops train --model demo --dataset data
qsmlops verify --version-id <id>
qsmlops status
```

## Configuration

Environment selection: `QSMLOPS_ENV=development|testing|production`.

Layered resolution (later layers win):

1. built-in defaults
2. `configs/settings.<env>.yaml`
3. `QSMLOPS_*` environment variables (`QSMLOPS_HOME`, `QSMLOPS_DEBUG`,
   `QSMLOPS_LOG_LEVEL`, `QSMLOPS_JSON_LOGS`, `QSMLOPS_API_HOST`,
   `QSMLOPS_API_PORT`, `QSMLOPS_DB_URL`)
4. explicit overrides passed to `load_settings()`

State root: `QSMLOPS_HOME` (default `~/.qsmlops`). Layout:

```
<home>/
├── artifacts/          # content-addressed artifacts (SHA3 digests)
├── keys/               # trust anchors + (encrypted) secret keys
├── ledger/             # evidence.jsonl (hash chain)
├── registry/           # registry.sqlite3 (model lifecycle state)
├── platform/           # platform.sqlite3 (identities, audit mirror)
└── supervisor/         # learning state
```

## Tests

```bash
python -m pytest tests/ -q                 # everything
python -m pytest tests/test_foundation.py  # Part-1 foundation suite
```

Note: `tests/test_phase2_platform.py` contains pre-written Phase 2 tests for
not-yet-implemented features; failures there are expected until Phase 2.

## Logging

JSON-per-line in production (`json_logs: true`), human-readable in
development. All platform loggers live under the `qsmlops.` namespace; extra
fields (`event`, `service`, `actor`, `resource`) are indexed by the JSON
formatter for future telemetry integration.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ModuleNotFoundError: qsmlops` | run from repo root or `pip install -e .` |
| `PyYAML is required to load configs/...` | `pip install pyyaml` |
| Audit chain broken after manual file edit | expected — restore from backup; chain integrity is a security feature |
| Registry lock errors | only one process should own a platform home at a time (SQLite WAL single-writer) |
