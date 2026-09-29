"""Per-user mutation limits on the hosted API (Phase 20G).

Login limiting and forged X-Forwarded-For handling are covered by
test_phase6_api.py and the production-proxy browser test; this covers the
authenticated per-user, per-operation limit.
"""

from dataclasses import replace

from test_phase6_api import headers

pytest_plugins = ["test_tenant_schema", "test_phase6_api"]


def _entity(client, h, n):
    return client.post(
        "/api/v1/entities", headers=h, json={"display_name": f"Bank {n}", "sector": "banking"}
    )


def test_mutation_limit_is_per_user_and_reads_are_not_consumed(api):
    client = api["client"]
    state = client.app.state
    state.settings = replace(state.settings, mutation_limit=3)

    analyst = headers(api, "analyst")
    for n in range(3):
        assert _entity(client, analyst, n).status_code == 201
    limited = _entity(client, analyst, 99)
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"

    # The limit belongs to the user: another member of the organization is unaffected,
    # and a limited user can still read.
    assert _entity(client, headers(api, "supervisor"), 100).status_code == 201
    assert client.get("/api/v1/entities", headers=analyst).status_code == 200
