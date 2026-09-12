# SAT-SA — single-process container: the sat-sa CLI + the FastAPI/
# Jinja2 UI, both backed by a SQLite file mounted as a volume.
#
# Verification status (reconciled P32, September 2026): this image's
# `docker build` and a `sat-sa ... doctor` smoke run were verified on
# a GitHub-hosted Ubuntu runner by the repository's CI
# (`docker-build-smoke` job in .github/workflows/ci.yml; latest green
# run 34667939977 at commit a72f079). This is a build/smoke proof on
# hosted CI infrastructure — NOT a completed deployment to a target
# NCIIPC air-gapped host, which has not been performed. See
# docs/deployment.md for the native (non-container) path and
# docs/CLAIMS.md for the exact claims boundary.

FROM python:3.13-slim AS base

# Build tooling for any dependency without a prebuilt wheel for this
# platform (numpy/scipy usually ship wheels; kept minimal otherwise).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install --no-cache-dir -e .

# Runtime data lives on a volume — the image itself carries no
# database or key material.
RUN mkdir -p /data/db /data/keys
VOLUME ["/data"]

ENV SATSA_DB=/data/db/satsa.db \
    SATSA_TRUST_KEY_DIR=/data/keys \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# Fails closed if the install is broken, per `sat-sa doctor` (P24) —
# not just "the process started."
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD sat-sa --db ${SATSA_DB} --trust-key-dir ${SATSA_TRUST_KEY_DIR} doctor || exit 1

CMD ["python", "scripts/serve_ui.py", \
     "--db", "/data/db/satsa.db", \
     "--trust-key-dir", "/data/keys", \
     "--host", "0.0.0.0", "--port", "8000"]
