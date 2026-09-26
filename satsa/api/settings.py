"""Explicit API edge settings, independent of domain algorithms."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ApiSettings:
    secure_cookies: bool = True
    session_ttl: int = 28800
    allowed_hosts: tuple[str, ...] = ("localhost", "127.0.0.1", "testserver")
    allowed_origins: tuple[str, ...] = ()
    max_request_bytes: int = 17 * 1024 * 1024
    mutation_limit: int = 30
    read_limit: int = 300

    def __post_init__(self):
        if self.session_ttl <= 0 or self.mutation_limit < 1 or self.read_limit < 1:
            raise ValueError("invalid API limits")
        if "*" in self.allowed_hosts or any(
            "*" in o or not o.startswith(("https://", "http://"))
            for o in self.allowed_origins
        ):
            raise ValueError("explicit hosts and origins are required")

    @classmethod
    def from_env(cls):
        return cls(
            secure_cookies=os.getenv("SATSA_COOKIE_SECURE", "true").lower() == "true",
            session_ttl=int(os.getenv("SATSA_SESSION_TTL_SECONDS", "28800")),
            allowed_hosts=tuple(
                x.strip()
                for x in os.getenv("SATSA_ALLOWED_HOSTS", "localhost,127.0.0.1").split(
                    ","
                )
                if x.strip()
            ),
            allowed_origins=tuple(
                x.strip()
                for x in os.getenv("SATSA_ALLOWED_ORIGINS", "").split(",")
                if x.strip()
            ),
            max_request_bytes=int(
                os.getenv("SATSA_MAX_REQUEST_BYTES", str(17 * 1024 * 1024))
            ),
            mutation_limit=int(os.getenv("SATSA_MUTATION_RATE_LIMIT", "30")),
            read_limit=int(os.getenv("SATSA_READ_RATE_LIMIT", "300")),
        )
