"""Phase 22: foundation-model provider fallback (satsa/llm).

Providers are mocked at the HTTP / Bedrock-client boundary, so the real
provider adapters, failure classification, chain and briefing code run.
"""

import json
import logging

import httpx
import pytest

from satsa.llm import chain as chain_mod
from satsa.llm.briefing import deterministic, validate
from satsa.llm.chain import run_chain
from satsa.llm.config import ChainConfig, LLMConfigurationError, ProviderSpec, load_chain
from satsa.llm.providers import ProviderPermanent, ProviderTransient, openai_compatible

GOOD = json.dumps({"summary": "Two signal findings.", "key_points": ["escalation gap"]})
KEY = "sk-test-DO-NOT-LEAK-1234567890"


def spec(name, retries=1, kind="openai_compatible"):
    return ProviderSpec(name=name, kind=kind, model=f"{name}-model", base_url=f"https://{name}.example/v1",
                        api_key_env=f"{name.upper()}_KEY", timeout_s=5, max_retries=retries)


def scripted(outcomes):
    """Callers returning/raising per provider name, recording calls."""
    calls = []

    def call(s, messages):
        calls.append(s.name)
        result = outcomes[s.name].pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    return {"openai_compatible": call, "bedrock": call}, calls


def run(outcomes, providers, deterministic_fn=None, deadline=60.0):
    callers, calls = scripted(outcomes)
    result = run_chain(ChainConfig(tuple(providers), deadline), [{"role": "user", "content": "x"}],
                       validate, deterministic=deterministic_fn, callers=callers, sleep=lambda s: None)
    return result, calls


FACTS = {"risk_total": 42.0, "confidence_bucket": "medium", "risk_dimensions": {"anomaly": 9.0},
         "finding_states": {"signal": 2}, "signal_rules": ["r1"], "recommendation_count": 1,
         "advisory_model": None}


def test_1_primary_succeeds():
    result, calls = run({"a": [GOOD]}, [spec("a"), spec("b")])
    assert (result.status, result.provider, result.fallback_level) == ("generated", "a", 1)
    assert calls == ["a"]


@pytest.mark.parametrize("failure, code", [
    (ProviderTransient("timeout", "PROVIDER_TIMEOUT"), "PROVIDER_TIMEOUT"),
    (ProviderTransient("429", "PROVIDER_RATE_LIMITED"), "PROVIDER_RATE_LIMITED"),
    (ProviderTransient("503", "MODEL_UNAVAILABLE"), "MODEL_UNAVAILABLE"),
])
def test_2_3_4_transient_primary_retries_once_then_secondary(failure, code):
    result, calls = run({"a": [failure, failure], "b": [GOOD]}, [spec("a", retries=1), spec("b")])
    assert (result.status, result.provider, result.fallback_level) == ("generated", "b", 2)
    assert calls == ["a", "a", "b"]  # bounded: one retry of the transient provider
    assert [a.code for a in result.attempts[:2]] == [code, code]


def test_5_invalid_credentials_are_not_retried():
    result, calls = run({"a": [ProviderPermanent("401")], "b": [GOOD]}, [spec("a", retries=3), spec("b")])
    assert calls == ["a", "b"] and result.provider == "b"
    assert result.attempts[0].outcome == "permanent"


def test_6_8_all_providers_down_uses_deterministic_fallback():
    down = ProviderTransient("503")
    result, _ = run({"a": [down, down], "b": [down, down]}, [spec("a"), spec("b")],
                    deterministic_fn=lambda: deterministic(FACTS))
    assert result.status == "deterministic" and result.fallback_level == 3
    assert "without a language model" in result.output["summary"]


def test_7_alternate_third_provider_succeeds():
    bad = ProviderPermanent("400")
    result, _ = run({"a": [bad], "b": [bad], "c": [GOOD]}, [spec("a"), spec("b"), spec("c", kind="bedrock")])
    assert (result.provider, result.fallback_level) == ("c", 3)


def test_9_abstention_codes():
    result, _ = run({}, [])
    assert (result.status, result.abstain_reason) == ("abstained", "MODEL_NOT_CONFIGURED")
    rate = ProviderTransient("429", "PROVIDER_RATE_LIMITED")
    result, _ = run({"a": [rate, rate]}, [spec("a")])
    assert (result.status, result.abstain_reason) == ("abstained", "PROVIDER_RATE_LIMITED")


def test_10_malformed_output_is_rejected_and_falls_through():
    result, calls = run({"a": ["not json"], "b": [json.dumps({"summary": "x" * 5000, "key_points": ["y"]})],
                         "c": [json.dumps({"summary": "ok", "key_points": ["p"], "decision": "confirm"})]},
                        [spec("a"), spec("b"), spec("c")])
    assert result.status == "abstained" and result.abstain_reason == "MODEL_OUTPUT_INVALID"
    assert [a.outcome for a in result.attempts] == ["invalid_output"] * 3


def test_deadline_bounds_the_whole_chain():
    ticks = iter([0.0, 0.0, 100.0, 100.0, 100.0, 100.0, 100.0])
    callers, calls = scripted({"a": [ProviderTransient("t", "PROVIDER_TIMEOUT")], "b": [GOOD]})
    result = run_chain(ChainConfig((spec("a"), spec("b")), 10.0), [], validate, callers=callers,
                       sleep=lambda s: None, clock=lambda: next(ticks))
    assert calls == ["a"] and result.abstain_reason == "PROVIDER_TIMEOUT"


# -- real adapter classification against HTTP responses -------------------------

def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.mark.parametrize("status, kind, code", [
    (429, ProviderTransient, "PROVIDER_RATE_LIMITED"), (503, ProviderTransient, "MODEL_UNAVAILABLE"),
    (401, ProviderPermanent, "MODEL_NOT_CONFIGURED"), (400, ProviderPermanent, "MODEL_UNAVAILABLE"),
])
def test_openai_compatible_status_classification(status, kind, code):
    with pytest.raises(kind) as info:
        openai_compatible(spec("nim"), [], client=_client(lambda r: httpx.Response(status)),
                          environ={"NIM_KEY": KEY})
    assert info.value.code == code and KEY not in str(info.value)


def test_openai_compatible_timeout_and_success():
    def timeout(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(ProviderTransient) as info:
        openai_compatible(spec("nim"), [], client=_client(timeout), environ={"NIM_KEY": KEY})
    assert info.value.code == "PROVIDER_TIMEOUT"
    seen = {}

    def ok(request):
        seen["auth"] = request.headers["authorization"]
        return httpx.Response(200, json={"choices": [{"message": {"content": GOOD}}]})

    assert openai_compatible(spec("nim"), [], client=_client(ok), environ={"NIM_KEY": KEY}) == GOOD
    assert seen["auth"] == f"Bearer {KEY}"


def test_missing_key_is_permanent_not_a_crash():
    with pytest.raises(ProviderPermanent, match="NIM_KEY is not set"):
        openai_compatible(spec("nim"), [], client=_client(lambda r: httpx.Response(200)), environ={})


# -- configuration -----------------------------------------------------------------

def test_chain_configuration_rejects_keys_and_bad_entries():
    good = [{"name": "nim", "kind": "openai_compatible", "base_url": "https://integrate.api.nvidia.com/v1",
             "model": "m", "api_key_env": "NVIDIA_API_KEY"},
            {"name": "bedrock", "kind": "bedrock", "model": "amazon.nova-lite-v1:0", "region": "ap-south-1"}]
    config = load_chain({"SATSA_LLM_CHAIN": json.dumps(good)})
    assert [p.name for p in config.providers] == ["nim", "bedrock"]
    assert load_chain({}).providers == ()
    for bad in ([{**good[0], "api_key": KEY}], [{**good[0], "base_url": "http://x/v1"}],
                [{**good[0], "kind": "gemini"}], [{**good[0], "extra_headers": {"Authorization": KEY}}],
                [good[0], good[0]]):
        with pytest.raises(LLMConfigurationError):
            load_chain({"SATSA_LLM_CHAIN": json.dumps(bad)})


# -- secrets and authority -----------------------------------------------------------

def test_14_no_secret_in_results_or_logs(caplog):
    caplog.set_level(logging.INFO, logger="satsa.llm")

    def handler(request):
        return httpx.Response(401)

    def call(s, messages):
        return openai_compatible(s, messages, client=_client(handler), environ={"A_KEY": KEY})

    result = run_chain(ChainConfig((spec("a"),)), [{"role": "user", "content": "facts"}], validate,
                       deterministic=lambda: deterministic(FACTS),
                       callers={"openai_compatible": call}, sleep=lambda s: None)
    assert KEY not in json.dumps(result.to_record())
    assert KEY not in caplog.text


def test_15_output_schema_cannot_carry_privileged_fields():
    for extra in ("decision", "risk_total", "priority", "action"):
        with pytest.raises(ValueError):
            validate({"summary": "s", "key_points": ["p"], extra: "x"})
