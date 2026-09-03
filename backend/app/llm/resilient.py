from __future__ import annotations

import logging

from .base import LLMProvider, T
from .mock import MockLLMProvider

logger = logging.getLogger(__name__)


class ResilientLLMProvider(LLMProvider):
    """Wrap a real provider with timeout/error handling and an explicit mock fallback.

    In production the fallback is disabled by configuration, so a real provider
    failure surfaces as an error instead of being silently presented as success.
    When a fallback happens, ``provider_label`` is marked ``...:fallback`` so the
    agent trace records which path actually produced the result.
    """

    def __init__(self, primary: LLMProvider, allow_fallback: bool = True):
        self.primary = primary
        self.allow_fallback = allow_fallback
        self._last_provider = "primary"

    @property
    def provider_label(self) -> str:
        if self._last_provider == "fallback":
            return f"{self.primary.provider_label}:fallback"
        return self.primary.provider_label

    async def structured(self, prompt: str, output_schema: type[T]) -> T:
        try:
            self._last_provider = "primary"
            return await self.primary.structured(prompt, output_schema)
        except Exception as exc:
            if not self.allow_fallback:
                raise
            logger.warning(
                "LLM provider %s failed (%s: %s); falling back to mock parser",
                self.primary.provider_label,
                type(exc).__name__,
                exc,
            )
            self._last_provider = "fallback"
            return await MockLLMProvider().structured(prompt, output_schema)
