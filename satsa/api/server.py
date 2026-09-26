"""Versioned SAT-SA API process entry point: ``python -m satsa.api.server``."""

import logging
import os

import uvicorn

from satsa.api import create_app
from satsa.api.runtime import build_runtime
from satsa.api.settings import ApiSettings


def main():
    logging.basicConfig(
        level=os.getenv("SATSA_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    engine, audit, identity, storage, key_dir = build_runtime()
    settings = ApiSettings.from_env()
    app = create_app(
        engine,
        storage=storage,
        audit=audit,
        identity_service=identity,
        settings=settings,
        trust_key_dir=key_dir,
    )
    try:
        uvicorn.run(
            app,
            host=os.getenv("SATSA_API_HOST", "127.0.0.1"),
            port=int(os.getenv("SATSA_API_PORT", "8000")),
            proxy_headers=os.getenv("SATSA_TRUST_PROXY_HEADERS", "false").lower()
            == "true",
            forwarded_allow_ips=os.getenv("SATSA_TRUSTED_PROXIES", "127.0.0.1"),
            log_level=os.getenv("SATSA_LOG_LEVEL", "info").lower(),
        )
    finally:
        engine.close()


if __name__ == "__main__":
    main()
