"""Foundation-model provider configuration (not the Phase 21 ML model).

The chain is configured by ``SATSA_LLM_CHAIN``: a JSON list, tried in order.
It holds no credentials; each entry names the environment variable its key is
read from, and on AWS those variables are filled from Secrets Manager for the
worker only.

    (example with NVIDIA NIM, OpenRouter and Bedrock: docs/LLM.md)

Kinds: ``openai_compatible`` (NVIDIA NIM, OpenRouter, or any endpoint that
speaks the OpenAI chat-completions API, such as a provider the operator names
with its own base_url) and ``bedrock`` (Amazon Bedrock Converse, authenticated
by the instance role; no key). Unset or empty chain = model assistance off.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from urllib.parse import urlparse

KINDS = ("openai_compatible", "bedrock")


class LLMConfigurationError(ValueError):
    """The chain configuration itself is invalid (not a provider failure)."""


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    kind: str
    model: str
    base_url: str = ""
    api_key_env: str = ""
    region: str = ""
    timeout_s: float = 20.0
    max_retries: int = 1
    enabled: bool = True
    extra_headers: dict = field(default_factory=dict)

    def api_key(self, environ=None) -> str | None:
        if not self.api_key_env:
            return None
        return (environ if environ is not None else os.environ).get(self.api_key_env) or None


@dataclass(frozen=True)
class ChainConfig:
    providers: tuple[ProviderSpec, ...]
    # Upper bound on the whole chain for one request, retries included.
    deadline_s: float = 90.0


def _spec(raw: dict, index: int) -> ProviderSpec:
    if not isinstance(raw, dict):
        raise LLMConfigurationError(f"provider #{index} must be an object")
    unknown = set(raw) - {"name", "kind", "model", "base_url", "api_key_env", "region",
                          "timeout_s", "max_retries", "enabled", "extra_headers"}
    if unknown:
        raise LLMConfigurationError(f"provider #{index}: unknown fields {sorted(unknown)}")
    kind = raw.get("kind")
    if kind not in KINDS:
        raise LLMConfigurationError(f"provider #{index}: kind must be one of {KINDS}")
    for key in ("name", "model"):
        if not isinstance(raw.get(key), str) or not raw[key].strip():
            raise LLMConfigurationError(f"provider #{index}: {key} is required")
    if kind == "openai_compatible":
        url = urlparse(str(raw.get("base_url", "")))
        if url.scheme != "https" or not url.netloc:
            raise LLMConfigurationError(f"provider #{index}: base_url must be an https URL")
        if not raw.get("api_key_env"):
            raise LLMConfigurationError(f"provider #{index}: api_key_env names the key variable")
    if "api_key" in raw or any("key" in k and k != "api_key_env" for k in raw):
        raise LLMConfigurationError("keys never go in SATSA_LLM_CHAIN; use api_key_env")
    timeout = float(raw.get("timeout_s", 20.0))
    retries = int(raw.get("max_retries", 1))
    if not 1 <= timeout <= 120 or not 0 <= retries <= 3:
        raise LLMConfigurationError(f"provider #{index}: timeout_s 1-120, max_retries 0-3")
    headers = raw.get("extra_headers") or {}
    if not isinstance(headers, dict) or any(h.lower() == "authorization" for h in headers):
        raise LLMConfigurationError(f"provider #{index}: extra_headers must not carry credentials")
    return ProviderSpec(
        name=raw["name"].strip(), kind=kind, model=raw["model"].strip(),
        base_url=str(raw.get("base_url", "")).rstrip("/"), api_key_env=raw.get("api_key_env", ""),
        region=raw.get("region", ""), timeout_s=timeout, max_retries=retries,
        enabled=bool(raw.get("enabled", True)), extra_headers=dict(headers),
    )


def load_chain(environ=None) -> ChainConfig:
    env = environ if environ is not None else os.environ
    raw = (env.get("SATSA_LLM_CHAIN") or "").strip()
    deadline = float(env.get("SATSA_LLM_DEADLINE_S", "90"))
    if not raw:
        return ChainConfig(providers=(), deadline_s=deadline)
    try:
        entries = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMConfigurationError("SATSA_LLM_CHAIN is not valid JSON") from exc
    if not isinstance(entries, list):
        raise LLMConfigurationError("SATSA_LLM_CHAIN must be a JSON list")
    specs = tuple(_spec(item, i) for i, item in enumerate(entries))
    names = [s.name for s in specs]
    if len(names) != len(set(names)):
        raise LLMConfigurationError("provider names must be unique")
    return ChainConfig(providers=tuple(s for s in specs if s.enabled), deadline_s=deadline)
