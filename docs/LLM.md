# Model-assisted capability and provider fallback

SAT-SA's analytics, risk, priorities, recommendations and the Phase 21
review-outcome ML model are deterministic or self-trained and never call a
language model. One capability uses foundation models: the **reviewer
briefing**, an advisory plain-language orientation for the supervisor, shown on
the run page (`GET /api/v1/runs/{run_id}/briefing`).

## Where it runs

LangGraph node `reviewer_briefing` (after `model_inference`, before the
`human_review` interrupt), and the same step on the standard path. The node
writes one record per run and never fails the run.

## Safety boundary

* Input: only structured, worker-computed fields (risk totals and dimensions,
  finding-state counts, signal rule names, recommendation count, advisory ML
  status). Uploaded evidence text never reaches a model, so content inside a
  submission cannot instruct it.
* Output: JSON `{"summary", "key_points"}` validated against a strict schema;
  any extra field (for example `decision` or `risk_total`) is rejected. The
  output is display-only; nothing reads it into findings, risk, priorities,
  recommendations or decisions. The supervisor decides.
* Provenance: provider, model, fallback level, attempts and a content digest
  are stored and bound into the TRUST-SAT finalization; altering them after
  finalization makes verification report `inconsistent`.
* Secrets: keys are never logged, stored in records, placed in graph state or
  given to the API or web containers.

## Fallback chain

`SATSA_LLM_CHAIN` (JSON list, in order) + key variables named by each entry:

```json
[
  {"name": "nim", "kind": "openai_compatible",
   "base_url": "https://integrate.api.nvidia.com/v1",
   "model": "<NIM model id>", "api_key_env": "NVIDIA_API_KEY",
   "timeout_s": 20, "max_retries": 1},
  {"name": "openrouter", "kind": "openai_compatible",
   "base_url": "https://openrouter.ai/api/v1",
   "model": "<OpenRouter model id>", "api_key_env": "OPENROUTER_API_KEY"},
  {"name": "bedrock", "kind": "bedrock",
   "model": "<Bedrock model id>", "region": "ap-south-1"}
]
```

Level 1..n: providers in order. Transient failures (timeout, connection error,
429, 5xx, Bedrock throttling or unavailability) are retried up to
`max_retries` with backoff, then the next provider is tried. Permanent failures
(missing or rejected key, bad request, unknown model) and invalid output move to
the next provider without retrying. `SATSA_LLM_DEADLINE_S` (default 90) bounds
the whole chain. Level n+1: a deterministic briefing from the same structured
fields (labelled as such). Codes when nothing is produced: `MODEL_NOT_CONFIGURED`,
`MODEL_UNAVAILABLE`, `PROVIDER_TIMEOUT`, `PROVIDER_RATE_LIMITED`,
`MODEL_OUTPUT_INVALID`.

Any OpenAI-compatible provider is added with `kind: openai_compatible` and its
own https `base_url`; there is no provider-specific code to write. Bedrock uses
the EC2 instance role (no key); the model must be enabled for the account.

## Configuration

* Local: environment variables (`SATSA_LLM_CHAIN`, key variables).
* AWS: one Secrets Manager secret `satsa/<env>/llm-providers`, a JSON object of
  those variables. `deploy/aws/deploy.sh` renders it to `/etc/satsa/llm.env`
  (mode 0600), which only the worker container reads. No secret = model
  assistance off (deterministic briefings); an invalid chain is logged and
  treated the same way, so a configuration mistake never stops analysis.

## Not claimed

No autonomous agent, no tool use by models, no model-made supervisory
decisions, no explainability claims. Briefings summarize; they do not judge.
