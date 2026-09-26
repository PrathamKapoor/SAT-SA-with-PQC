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
RUN pip install --no-cache-dir -e ".[postgres,s3]" \
    && useradd --system --uid 10001 --create-home satsa \
    && mkdir -p /data \
    && chown -R satsa:satsa /app /data

VOLUME ["/data"]

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER 10001:10001

EXPOSE 8000

CMD ["python", "-m", "satsa.api.server"]
