"""Provider calls with failure classification.

``ProviderTransient``: worth retrying or trying later (timeout, connection,
429, 5xx, provider throttling/unavailability). ``ProviderPermanent``: retrying
the same provider cannot help (bad or missing key, forbidden, bad request,
unknown model). Neither exception message ever contains a credential.
"""

from __future__ import annotations

import httpx

from satsa.llm.config import ProviderSpec


class ProviderError(Exception):
    code = "MODEL_UNAVAILABLE"


class ProviderTransient(ProviderError):
    def __init__(self, message: str, code: str = "MODEL_UNAVAILABLE"):
        super().__init__(message)
        self.code = code


class ProviderPermanent(ProviderError):
    def __init__(self, message: str, code: str = "MODEL_NOT_CONFIGURED"):
        super().__init__(message)
        self.code = code


def _classify_status(status: int, provider: str) -> ProviderError:
    if status == 429:
        return ProviderTransient(f"{provider}: rate limited (429)", "PROVIDER_RATE_LIMITED")
    if status >= 500:
        return ProviderTransient(f"{provider}: provider error ({status})", "MODEL_UNAVAILABLE")
    if status in (401, 403):
        return ProviderPermanent(f"{provider}: authentication rejected ({status})", "MODEL_NOT_CONFIGURED")
    return ProviderPermanent(f"{provider}: request rejected ({status})", "MODEL_UNAVAILABLE")


def openai_compatible(spec: ProviderSpec, messages: list[dict], *, client=None, environ=None) -> str:
    key = spec.api_key(environ)
    if not key:
        raise ProviderPermanent(f"{spec.name}: key variable {spec.api_key_env} is not set")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", **spec.extra_headers}
    body = {"model": spec.model, "messages": messages, "temperature": 0,
            "max_tokens": 700, "response_format": {"type": "json_object"}}
    http = client or httpx.Client(timeout=spec.timeout_s)
    try:
        response = http.post(f"{spec.base_url}/chat/completions", json=body, headers=headers,
                             timeout=spec.timeout_s)
    except httpx.TimeoutException as exc:
        raise ProviderTransient(f"{spec.name}: timed out after {spec.timeout_s}s", "PROVIDER_TIMEOUT") from exc
    except httpx.TransportError as exc:
        raise ProviderTransient(f"{spec.name}: connection failed ({type(exc).__name__})") from exc
    finally:
        if client is None:
            http.close()
    if response.status_code != 200:
        raise _classify_status(response.status_code, spec.name)
    try:
        return response.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ProviderPermanent(f"{spec.name}: unexpected response shape", "MODEL_OUTPUT_INVALID") from exc


_BEDROCK_TRANSIENT = {"ThrottlingException", "ServiceUnavailableException", "ModelNotReadyException",
                      "InternalServerException", "ModelTimeoutException"}


def bedrock(spec: ProviderSpec, messages: list[dict], *, client=None, environ=None) -> str:
    try:
        import boto3
        from botocore.config import Config
        from botocore.exceptions import BotoCoreError, ClientError, ReadTimeoutError
    except ImportError as exc:  # pragma: no cover - the image installs boto3
        raise ProviderPermanent(f"{spec.name}: boto3 is not installed") from exc
    runtime = client or boto3.client(
        "bedrock-runtime", region_name=spec.region or None,
        config=Config(read_timeout=spec.timeout_s, connect_timeout=5, retries={"max_attempts": 1}),
    )
    system = [{"text": m["content"]} for m in messages if m["role"] == "system"]
    convo = [{"role": m["role"], "content": [{"text": m["content"]}]} for m in messages if m["role"] != "system"]
    try:
        result = runtime.converse(modelId=spec.model, system=system, messages=convo,
                                  inferenceConfig={"temperature": 0, "maxTokens": 700})
    except ReadTimeoutError as exc:
        raise ProviderTransient(f"{spec.name}: timed out after {spec.timeout_s}s", "PROVIDER_TIMEOUT") from exc
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in _BEDROCK_TRANSIENT:
            raise ProviderTransient(f"{spec.name}: {code}",
                                    "PROVIDER_RATE_LIMITED" if code == "ThrottlingException" else "MODEL_UNAVAILABLE") from exc
        raise ProviderPermanent(f"{spec.name}: {code or 'request rejected'}") from exc
    except BotoCoreError as exc:
        raise ProviderTransient(f"{spec.name}: connection failed ({type(exc).__name__})") from exc
    try:
        return result["output"]["message"]["content"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderPermanent(f"{spec.name}: unexpected response shape", "MODEL_OUTPUT_INVALID") from exc


CALLERS = {"openai_compatible": openai_compatible, "bedrock": bedrock}
