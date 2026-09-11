# SAT-SA — single-process container: the sat-sa CLI + the FastAPI/
# Jinja2 UI, both backed by a SQLite file mounted as a volume.
#
# HONESTY NOTE (do not remove): this Dockerfile was authored but has
# NOT been built or run in the session that wrote it — no Docker
# daemon was available in that environment. It is consistent with
# requirements.txt / pyproject.toml and the verified-working
# scripts/serve_ui.py launcher, but "docker build" / "docker run"
# have not actually been exercised. Build and test this image before
# relying on it; do not treat its presence as proof it works. See
# docs/deployment.md for the native (non-container) path, which HAS
# been run and verified in-session.

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
