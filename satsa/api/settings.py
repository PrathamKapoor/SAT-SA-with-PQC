"""Explicit API edge settings, independent of domain algorithms."""

import ipaddress
import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class ApiSettings:
    secure_cookies: bool = True
    cookie_samesite: str = "lax"
    session_ttl: int = 28800
    allowed_hosts: tuple[str, ...] = ("localhost", "127.0.0.1", "testserver")
    allowed_origins: tuple[str, ...] = ()
    trust_proxy_headers: bool = False
    trusted_proxies: tuple[str, ...] = ()
    max_request_bytes: int = 17 * 1024 * 1024
    mutation_limit: int = 30
    read_limit: int = 300

    def __post_init__(self):
        if self.session_ttl <= 0 or self.mutation_limit < 1 or self.read_limit < 1:
            raise ValueError("invalid API limits")
        if self.cookie_samesite not in {"lax", "strict", "none"}:
            raise ValueError("SATSA_COOKIE_SAMESITE must be lax, strict, or none")
        if self.cookie_samesite == "none" and not self.secure_cookies:
            raise ValueError("SameSite=None cookies require Secure")
        if "*" in self.allowed_hosts or any(
            "*" in o or not o.startswith(("https://", "http://"))
            for o in self.allowed_origins
        ):
            raise ValueError("explicit hosts and origins are required")
        if not self.allowed_hosts:
            raise ValueError("at least one allowed host is required")
        if "*" in self.trusted_proxies:
            raise ValueError("wildcard trusted proxies are not allowed")
        try:
            for proxy in self.trusted_proxies:
                ipaddress.ip_network(proxy, strict=False)
        except ValueError as exc:
            raise ValueError("trusted proxies must be IP addresses or CIDRs") from exc
        if self.trust_proxy_headers and not self.trusted_proxies:
            raise ValueError(
                "trusted proxy headers require an explicit proxy allowlist"
            )

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None):
        env = os.environ if environ is None else environ
        mode = env.get("SATSA_ENVIRONMENT", "development").strip().lower()
        raw_secure = env.get("SATSA_COOKIE_SECURE", "true").strip().lower()
        if raw_secure not in {"true", "false"}:
            raise ValueError("SATSA_COOKIE_SECURE must be true or false")
        secure = raw_secure == "true"
        raw_proxy = env.get("SATSA_TRUST_PROXY_HEADERS", "false").strip().lower()
        if raw_proxy not in {"true", "false"}:
            raise ValueError("SATSA_TRUST_PROXY_HEADERS must be true or false")
        trust_proxy_headers = raw_proxy == "true"
        trusted_proxies = tuple(
            value.strip()
            for value in env.get("SATSA_TRUSTED_PROXIES", "").split(",")
            if value.strip()
        )
        hosts = tuple(
            x.strip()
            for x in env.get("SATSA_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
            if x.strip()
        )
        origins = tuple(
            x.strip()
            for x in env.get("SATSA_ALLOWED_ORIGINS", "").split(",")
            if x.strip()
        )
        same_site = env.get("SATSA_COOKIE_SAMESITE", "lax").strip().lower()
        if mode == "production":
            if not secure:
                raise ValueError("production requires secure cookies")
            if not env.get("SATSA_ALLOWED_HOSTS", "").strip():
                raise ValueError("production requires an explicit SATSA_ALLOWED_HOSTS")
            if any(host in {"localhost", "127.0.0.1", "testserver"} for host in hosts):
                raise ValueError(
                    "production host configuration cannot contain a development host"
                )
            if any(not origin.startswith("https://") for origin in origins):
                raise ValueError("production CORS origins must use HTTPS")
            if trust_proxy_headers and not env.get("SATSA_TRUSTED_PROXIES", "").strip():
                raise ValueError(
                    "production forwarded headers require SATSA_TRUSTED_PROXIES"
                )
        return cls(
            secure_cookies=secure,
            cookie_samesite=same_site,
            session_ttl=int(env.get("SATSA_SESSION_TTL_SECONDS", "28800")),
            allowed_hosts=hosts,
            allowed_origins=origins,
            trust_proxy_headers=trust_proxy_headers,
            trusted_proxies=trusted_proxies,
            max_request_bytes=int(
                env.get("SATSA_MAX_REQUEST_BYTES", str(17 * 1024 * 1024))
            ),
            mutation_limit=int(env.get("SATSA_MUTATION_RATE_LIMIT", "30")),
            read_limit=int(env.get("SATSA_READ_RATE_LIMIT", "300")),
        )
