from dataclasses import dataclass, field
from typing import Protocol

@dataclass
class ToolResult:
    success: bool
    data: dict = field(default_factory=dict)
    error: str | None = None
    metadata: dict = field(default_factory=dict)

class Connector(Protocol):
    def call(self, name: str, args: dict) -> ToolResult: ...
