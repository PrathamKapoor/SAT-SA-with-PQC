"""Capability-level fallback over the configured providers.

Level 1..n  configured providers in order (primary, secondary, alternate, ...)
Level n+1   deterministic result built from structured data, if the capability has one
otherwise   explicit abstention with a reason code

Retries: only ``ProviderTransient`` failures, at most ``max_retries`` per
provider, with a short backoff, all inside the chain deadline. Permanent
failures (bad key, bad request, unknown model) and invalid output move to the
next provider without retrying the same one. Nothing here raises for provider
problems: the caller always gets a ``ChainResult``.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Callable

from satsa.llm.config import ChainConfig
from satsa.llm.providers import CALLERS, ProviderError, ProviderPermanent, ProviderTransient

log = logging.getLogger("satsa.llm")

ABSTAIN_CODES = ("MODEL_NOT_CONFIGURED", "MODEL_UNAVAILABLE", "PROVIDER_TIMEOUT",
                 "PROVIDER_RATE_LIMITED", "MODEL_OUTPUT_INVALID", "INSUFFICIENT_EVIDENCE")


class OutputInvalid(ValueError):
    """The provider answered, but not with output matching the schema."""


@dataclass
class Attempt:
    provider: str
    model: str
    attempt: int
    outcome: str          # ok | transient | permanent | invalid_output | deadline
    code: str | None
    latency_ms: float


@dataclass
class ChainResult:
    status: str                       # generated | deterministic | abstained
    output: dict | None
    provider: str | None              # provider that produced the output
    model: str | None
    fallback_level: int | None        # 1 = primary; len(providers)+1 = deterministic
    abstain_reason: str | None
    attempts: list[Attempt] = field(default_factory=list)
    latency_ms: float = 0.0

    def to_record(self) -> dict:
        data = asdict(self)
        data["attempts"] = [asdict(a) for a in self.attempts]
        return data


def run_chain(
    config: ChainConfig,
    messages: list[dict],
    validate: Callable[[dict], dict],
    *,
    deterministic: Callable[[], dict] | None = None,
    callers=None,
    sleep=time.sleep,
    clock=time.monotonic,
    context: dict | None = None,
) -> ChainResult:
    callers = callers or CALLERS
    started = clock()
    deadline = started + config.deadline_s
    attempts: list[Attempt] = []
    last_code: str | None = None
    for level, spec in enumerate(config.providers, start=1):
        for attempt in range(1, spec.max_retries + 2):
            if clock() >= deadline:
                attempts.append(Attempt(spec.name, spec.model, attempt, "deadline", "PROVIDER_TIMEOUT", 0.0))
                last_code = "PROVIDER_TIMEOUT"
                break
            t0 = clock()
            try:
                text = callers[spec.kind](spec, messages)
                try:
                    parsed = json.loads(text)
                    output = validate(parsed)
                except (ValueError, TypeError) as exc:
                    raise OutputInvalid(str(exc)[:200]) from exc
            except ProviderTransient as exc:
                attempts.append(Attempt(spec.name, spec.model, attempt, "transient", exc.code,
                                        round((clock() - t0) * 1000, 1)))
                last_code = exc.code
                if attempt <= spec.max_retries and clock() + 0.5 * attempt < deadline:
                    sleep(0.5 * attempt)
                    continue
                break
            except ProviderPermanent as exc:
                attempts.append(Attempt(spec.name, spec.model, attempt, "permanent", exc.code,
                                        round((clock() - t0) * 1000, 1)))
                last_code = exc.code
                break
            except OutputInvalid:
                attempts.append(Attempt(spec.name, spec.model, attempt, "invalid_output",
                                        "MODEL_OUTPUT_INVALID", round((clock() - t0) * 1000, 1)))
                last_code = "MODEL_OUTPUT_INVALID"
                break
            except ProviderError as exc:  # any other classified provider error
                attempts.append(Attempt(spec.name, spec.model, attempt, "permanent", exc.code,
                                        round((clock() - t0) * 1000, 1)))
                last_code = exc.code
                break
            attempts.append(Attempt(spec.name, spec.model, attempt, "ok", None,
                                    round((clock() - t0) * 1000, 1)))
            result = ChainResult("generated", output, spec.name, spec.model, level, None, attempts,
                                 round((clock() - started) * 1000, 1))
            _log(result, context)
            return result
    if deterministic is not None:
        result = ChainResult("deterministic", deterministic(), None, None, len(config.providers) + 1,
                             None, attempts, round((clock() - started) * 1000, 1))
    else:
        reason = "MODEL_NOT_CONFIGURED" if not config.providers else (last_code or "MODEL_UNAVAILABLE")
        result = ChainResult("abstained", None, None, None, None, reason, attempts,
                             round((clock() - started) * 1000, 1))
    _log(result, context)
    return result


def _log(result: ChainResult, context: dict | None) -> None:
    # Identifiers and outcomes only: never prompts, outputs or credentials.
    log.info("llm capability result", extra={
        **(context or {}), "status": result.status, "provider": result.provider,
        "model": result.model, "fallback_level": result.fallback_level,
        "attempts": len(result.attempts), "abstain_reason": result.abstain_reason,
        "latency_ms": result.latency_ms,
    })
