# Hosted presentation image for Render: the SAT-SA API, the analysis worker
# and the Next.js workbench in one container (scripts/render_stack.py).
# Render's free web services have no private network between services, so
# the API stays on 127.0.0.1 and only the web server is public on $PORT.
# Demo state only: SQLite and local artifact storage, rebuilt on each start.
# Production deployments use deploy/compose.production.yml instead.
#
# Build from the repository root:  docker build -f deploy/render/Dockerfile .

ARG NODE_VERSION=24.21.0-trixie-slim

FROM node:${NODE_VERSION} AS web-dependencies
WORKDIR /app
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM node:${NODE_VERSION} AS web-builder
WORKDIR /app
COPY --from=web-dependencies /app/node_modules ./node_modules
COPY web/ .
ENV NODE_ENV=production
RUN npm run build

FROM node:${NODE_VERSION} AS node-runtime

FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install --no-cache-dir -e . \
    && apt-get purge -y --auto-remove build-essential \
    && apt-get update && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --create-home satsa \
    && mkdir -p /data \
    && chown -R satsa:satsa /app /data

COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=web-builder --chown=satsa:satsa /app/.next/standalone /web
COPY --from=web-builder --chown=satsa:satsa /app/.next/static /web/.next/static
COPY --from=web-builder --chown=satsa:satsa /app/public /web/public

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NODE_ENV=production \
    PORT=10000

USER 10001:10001

EXPOSE 10000

CMD ["python", "scripts/render_stack.py", "--data-dir", "/data/satsa", "--web-dir", "/web"]
