# SAT-SA backend image. The default command serves the tenant-scoped API
# (`python -m satsa.api.server`, port 8000). docker-compose.saas.yml runs the
# same image as separate services: `migrate` (schema upgrade), `key-init`
# (TRUST-SAT signing key), `api` and `worker` (`sat-sa-worker`), with
# PostgreSQL and S3-compatible storage. The `sat-sa` CLI and the offline
# FastAPI/Jinja2 UI are installed too and can be run with `--entrypoint
# sat-sa` against a SQLite file on the /data volume. The Next.js web UI has
# its own image (web/Dockerfile).
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
    # The compiler is needed only to install dependencies; the runtime image
    # keeps no toolchain and takes pending Debian security updates.
    && apt-get purge -y --auto-remove build-essential \
    && apt-get update && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    # The runtime never installs packages. pip's vendored msgpack and
    # pkg_resources were the image's only fixable scanner findings and no newer
    # pip vendors fixed versions, so pip is removed instead (CI image-scan).
    && python -m pip uninstall -y pip \
    && useradd --system --uid 10001 --create-home satsa \
    && mkdir -p /data \
    && chown -R satsa:satsa /app /data

VOLUME ["/data"]

# The commit this image was built from; deploy/aws/publish.sh passes it.
ARG SATSA_RELEASE=unreleased
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SATSA_RELEASE=${SATSA_RELEASE}

USER 10001:10001

EXPOSE 8000

CMD ["python", "-m", "satsa.api.server"]
