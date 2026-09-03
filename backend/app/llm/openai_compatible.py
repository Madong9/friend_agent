from __future__ import annotations

import json
import logging
from time import perf_counter
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError

from .base import LLMProvider, LLMProviderError, T

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(LLMProvider):
    """Small OpenAI-compatible adapter suitable for Qwen, DeepSeek and similar APIs."""

    provider_label = "openai_compatible"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
        response_format_mode: str = "auto",
        trust_env: bool = False,
    ):
        if not base_url or not model:
            raise ValueError("LLM_BASE_URL and LLM_MODEL are required")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.transport = transport
        self.trust_env = trust_env
        if response_format_mode not in {"auto", "json_schema", "json_object"}:
            raise ValueError("unsupported LLM response format mode")
        self.response_format_mode = response_format_mode

    def _resolved_response_format(self) -> str:
        if self.response_format_mode != "auto":
            return self.response_format_mode
        hostname = (urlparse(self.base_url).hostname or "").lower()
        model = self.model.lower()
        # DeepSeek and GLM Chat Completions use json_object. Model detection is
        # necessary when an institutional gateway hides the upstream provider
        # behind its own OpenAI-compatible hostname.
        uses_json_object = (
            hostname.endswith("deepseek.com")
            or hostname.endswith("bigmodel.cn")
            or model.startswith("glm-")
        )
        return "json_object" if uses_json_object else "json_schema"

    async def structured(self, prompt: str, output_schema: type[T]) -> T:
        started_at = perf_counter()
        response: httpx.Response | None = None
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        schema = output_schema.model_json_schema()
        response_format_mode = self._resolved_response_format()
        response_format = (
            {"type": "json_object"}
            if response_format_mode == "json_object"
            else {
                "type": "json_schema",
                "json_schema": {
                    "name": output_schema.__name__,
                    "schema": schema,
                },
            }
        )
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return only JSON matching this JSON Schema exactly: "
                        + json.dumps(schema, ensure_ascii=False)
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": response_format,
            "temperature": 0,
            "max_tokens": 1200,
        }
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                transport=self.transport,
                trust_env=self.trust_env,
            ) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions", headers=headers, json=payload
                )
                response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            if not content:
                raise ValueError("empty model content")
            if isinstance(content, str):
                content = json.loads(content)
            return output_schema.model_validate(content)
        except httpx.HTTPError as exc:
            error_response = (
                exc.response if isinstance(exc, httpx.HTTPStatusError) else response
            )
            self._log_failure(exc, started_at, error_response)
            raise LLMProviderError(
                f"LLM provider returned an unusable {output_schema.__name__} response"
            ) from exc
        except (
            json.JSONDecodeError,
            ValidationError,
            KeyError,
            IndexError,
            TypeError,
            ValueError,
        ) as exc:
            self._log_failure(exc, started_at, response)
            raise LLMProviderError(
                f"LLM provider returned an unusable {output_schema.__name__} response"
            ) from exc

    def _log_failure(
        self,
        exc: Exception,
        started_at: float,
        response: httpx.Response | None,
    ) -> None:
        """Log diagnostics without request, response, prompt, or credentials."""
        hostname = urlparse(self.base_url).hostname or "unknown"
        status_code = response.status_code if response is not None else "none"
        logger.warning(
            "LLM call failed exception_type=%s elapsed_seconds=%.3f "
            "hostname=%s model=%s status_code=%s",
            type(exc).__name__,
            perf_counter() - started_at,
            hostname,
            self.model,
            status_code,
        )
