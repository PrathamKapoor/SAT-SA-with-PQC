"""Phase 22: the model-assisted briefing inside the real LangGraph run.

Providers are mocked at the adapter boundary; the graph, checkpointer, worker,
human-review interrupt and TRUST-SAT finalization are the real ones, on SQLite
and (with SATSA_TEST_POSTGRES_DSN) PostgreSQL.
"""

import json

import pytest

from satsa.llm import providers
from satsa.llm.providers import ProviderTransient
from test_phase6_api import dataset, headers

pytest_plugins = ["test_tenant_schema", "test_phase6_api"]

CHAIN = json.dumps([
    {"name": "nim", "kind": "openai_compatible", "base_url": "https://integrate.api.nvidia.com/v1",
     "model": "primary-model", "api_key_env": "NVIDIA_API_KEY", "max_retries": 1},
    {"name": "openrouter", "kind": "openai_compatible", "base_url": "https://openrouter.ai/api/v1",
     "model": "secondary-model", "api_key_env": "OPENROUTER_API_KEY"},
])
SECRET = "nvapi-test-DO-NOT-LEAK"


@pytest.fixture
def providers_down_then_up(monkeypatch):
    monkeypatch.setenv("SATSA_LLM_CHAIN", CHAIN)
    monkeypatch.setenv("NVIDIA_API_KEY", SECRET)
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET + "-2")
    calls = []

    def call(spec, messages):
        calls.append(spec.name)
        # Evidence text never reaches the model: only structured facts.
        assert "facts" in messages[1]["content"]
        if spec.name == "nim":
            raise ProviderTransient("nim: provider error (503)")
        return json.dumps({"summary": "Signals concentrated in escalation.", "key_points": ["check escalations"]})

    monkeypatch.setitem(providers.CALLERS, "openai_compatible", call)
    return calls


def test_fallback_in_graph_then_human_review_then_trust_sat(api, providers_down_then_up):
    from satsa.analysis.execution import AnalysisExecutionWorker

    c = api["client"]
    *_, version, _ = dataset(api)
    run = c.post("/api/v1/runs", headers=headers(api, key="llm-run"),
                 json={"submission_version_id": version["id"], "execution_mode": "graph"}).json()["id"]
    worker = AnalysisExecutionWorker(api["db"], worker_id="llm-1", audit=api["audit"],
                                     trust_key_dir=str(api["keys"]))
    # The graph stops at the human-review interrupt after the fallback.
    assert worker.run_once() == "awaiting_review"
    assert providers_down_then_up == ["nim", "nim", "openrouter"]
    briefing = c.get(f"/api/v1/runs/{run}/briefing", headers=headers(api, "viewer")).json()
    assert (briefing["status"], briefing["provider"], briefing["fallback_level"]) == ("generated", "openrouter", 2)
    assert [a["outcome"] for a in briefing["attempts"]] == ["transient", "transient", "ok"]
    assert SECRET not in json.dumps(briefing)

    # The model's output changed nothing the supervisor decides on.
    risk_before = c.get(f"/api/v1/runs/{run}/risk", headers=headers(api)).json()["content_digest"]

    # Supervisor decides; a fresh worker (restart) resumes the checkpointed graph.
    assert c.post(f"/api/v1/runs/{run}/decision", headers=headers(api, "supervisor"),
                  json={"action": "confirm", "reason": "reviewed"}).status_code == 201
    restarted = AnalysisExecutionWorker(api["db"], worker_id="llm-2", audit=api["audit"],
                                        trust_key_dir=str(api["keys"]))
    assert restarted.run_once() in {"completed", "partial"}
    assert providers_down_then_up == ["nim", "nim", "openrouter"]  # not called again on resume
    assert c.get(f"/api/v1/runs/{run}/risk", headers=headers(api)).json()["content_digest"] == risk_before
    assert c.post(f"/api/v1/runs/{run}/verify", headers=headers(api)).json()["status"] == "verified"
    final = api["db"].query_one("SELECT canonical_json FROM satsa_trust_finalizations WHERE run_id=?", (run,))
    bound = json.loads(final["canonical_json"])["reviewer_briefing"]
    assert (bound["provider"], bound["model"], bound["fallback_level"]) == ("openrouter", "secondary-model", 2)
    assert SECRET not in final["canonical_json"]

    # An altered briefing after finalization is detected.
    api["db"].execute("UPDATE satsa_llm_outputs SET provider='nim' WHERE run_id=?", (run,))
    assert c.post(f"/api/v1/runs/{run}/verify", headers=headers(api)).json()["status"] == "inconsistent"


def test_no_providers_configured_gives_deterministic_briefing(api, monkeypatch):
    from satsa.analysis.execution import AnalysisExecutionWorker

    monkeypatch.delenv("SATSA_LLM_CHAIN", raising=False)
    c = api["client"]
    *_, version, _ = dataset(api)
    run = c.post("/api/v1/runs", headers=headers(api, key="det-run"),
                 json={"submission_version_id": version["id"], "execution_mode": "standard"}).json()["id"]
    worker = AnalysisExecutionWorker(api["db"], worker_id="det", audit=api["audit"], trust_key_dir=str(api["keys"]))
    assert worker.run_once() == "awaiting_review"
    briefing = c.get(f"/api/v1/runs/{run}/briefing", headers=headers(api)).json()
    assert briefing["status"] == "deterministic" and briefing["provider"] is None
    assert briefing["attempts"] == [] and "without a language model" in briefing["output"]["summary"]
