from dataclasses import dataclass, field
from typing import Protocol

@dataclass
class AgentResult:
    final_answer: str
    actions: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    decision_summary: str = ""
    approval_state: str = "not_required"
    outcome: str = ""
    metadata: dict = field(default_factory=dict)

@dataclass
class TaskContext:
    scenario_id: str
    user_request: str
    initial_state: dict
    available_tools: list[str]
    connector: object

class Agent(Protocol):
    version: str
    def apply(self, task_context: TaskContext) -> AgentResult: ...
