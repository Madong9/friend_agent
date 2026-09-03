from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMProviderError(RuntimeError):
    """Safe provider-boundary error that never includes credentials."""


class LLMProvider(ABC):
    """Only structured, validated output crosses the provider boundary."""

    provider_label = "llm"

    @abstractmethod
    async def structured(self, prompt: str, output_schema: type[T]) -> T:
        raise NotImplementedError
