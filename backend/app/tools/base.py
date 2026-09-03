from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class BaseTool(ABC):
    name: str
    description: str
    input_schema: type[BaseModel]

    @abstractmethod
    async def execute(self, tool_input: BaseModel) -> Any:
        raise NotImplementedError
