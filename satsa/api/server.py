"""Versioned SAT-SA API process entry point: ``python -m satsa.api.server``."""

import logging
import os

import uvicorn

from qsmlops.core.logging import configure_logging
from satsa.api import create_app
from satsa.api.runtime import build_runtime
from satsa.api.settings import ApiSettings


def main():
    logging.basicConfig(
        level=os.getenv("SATSA_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    configure_logging(
        os.getenv("SATSA_LOG_LEVEL", "INFO"),
        json_format=os.getenv("SATSA_ENVIRONMENT", "development").lower()
        == "production",
    )
    settings = ApiSettings.from_env()
    engine, audit, identity, storage, key_dir = build_runtime()
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
            proxy_headers=settings.trust_proxy_headers,
            forwarded_allow_ips=(
                ",".join(settings.trusted_proxies) if settings.trusted_proxies else ""
            ),
            log_level=os.getenv("SATSA_LOG_LEVEL", "info").lower(),
        )
    finally:
        storage.close()
        engine.close()


if __name__ == "__main__":
    main()
