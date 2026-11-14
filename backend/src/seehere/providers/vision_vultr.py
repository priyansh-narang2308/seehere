"""Vision with structured JSON through Vultr Serverless Inference (OpenAI-compatible chat API).

Every reply is parsed and validated against the requested JSON schema here, whatever the
provider claims to enforce. An invalid reply is retried once with the validation error fed back;
a second invalid reply raises `VisionOutputInvalid`, and nothing unvalidated is ever returned.

Status (ADR-006): VISION_STRUCTURED is DOCUMENTED, not TESTED. A live call spends account credit,
so it runs only with the owner's approval (`SEEHERE_LIVE_VULTR_VISION=1`, see
tests/test_vision.py). Until then the pipeline does not call this adapter unless
`VISION_PROVIDER=vultr` is set explicitly.
"""

from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import Any

import httpx
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from pydantic import SecretStr

from seehere.providers.base import Capability, ProviderInfo, VerificationState
from seehere.providers.errors import ProviderError

MAX_IMAGE_BYTES = 20 * 1024 * 1024  # documented input limit


class VisionError(ProviderError):
    """The request failed. The message never contains the API key."""


class VisionOutputInvalid(VisionError):
    """The model's reply did not match the schema, twice."""


def validate(reply: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Parse and validate a reply. Raises ValueError with a short reason."""
    try:
        data = json.loads(reply)
    except json.JSONDecodeError as exc:
        raise ValueError(f"not valid JSON ({exc.msg})") from None
    try:
        Draft202012Validator(schema).validate(data)
    except ValidationError as exc:
        where = "/".join(str(p) for p in exc.absolute_path) or "(root)"
        raise ValueError(f"{where}: {exc.message[:200]}") from None
    if not isinstance(data, dict):  # pragma: no cover - the schema requires an object
        raise ValueError("expected a JSON object")
    return data


class VultrVisionAnalyzer:
    def __init__(
        self,
        api_key: SecretStr,
        *,
        base_url: str = "https://api.vultrinference.com/v1",
        model: str = "qwen3.8-flash-next",
        timeout_s: float = 90.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s
        self._transport = transport

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name=f"vultr:{self.model}",
            capabilities={Capability.VISION_STRUCTURED: VerificationState.DOCUMENTED},
            notes="Not yet exercised against the live service (calls cost credit).",
        )

    def _image_url(self, image_path: Path) -> str:
        data = image_path.read_bytes()
        if len(data) > MAX_IMAGE_BYTES:
            raise VisionError("image is larger than the documented 20 MB limit", retryable=False)
        mime = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
        return f"data:{mime};base64,{base64.b64encode(data).decode()}"

    def _ask(
        self, client: httpx.Client, messages: list[dict[str, Any]], schema: dict[str, Any]
    ) -> str:
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "visual_units", "schema": schema, "strict": True},
            },
        }
        try:
            r = client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key.get_secret_value()}"},
                json=body,
            )
        except httpx.HTTPError as exc:
            raise VisionError(f"request failed: {type(exc).__name__}") from None
        if r.status_code != 200:
            raise VisionError(f"Vultr returned HTTP {r.status_code}", status=r.status_code)
        try:
            return str(r.json()["choices"][0]["message"]["content"])
        except (ValueError, KeyError, IndexError, TypeError):
            raise VisionError("unexpected response format") from None

    def analyze(self, image_path: Path, prompt: str, json_schema: dict[str, Any]) -> dict[str, Any]:
        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": self._image_url(image_path)}},
                ],
            }
        ]
        with httpx.Client(timeout=self.timeout_s, transport=self._transport) as client:
            reply = self._ask(client, messages, json_schema)
            try:
                return validate(reply, json_schema)
            except ValueError as first:
                # One retry, telling the model exactly what was wrong.
                messages += [
                    {"role": "assistant", "content": reply[:4000]},
                    {
                        "role": "user",
                        "content": f"That reply was invalid: {first}. Reply again with JSON that "
                        "matches the schema exactly.",
                    },
                ]
                reply = self._ask(client, messages, json_schema)
                try:
                    return validate(reply, json_schema)
                except ValueError as second:
                    raise VisionOutputInvalid(f"invalid output twice: {second}") from None
