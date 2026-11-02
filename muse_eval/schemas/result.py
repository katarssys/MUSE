from dataclasses import dataclass, field
from typing import Protocol

CERTAINTIES = {"FACT", "SIGNAL", "INFERENCE", "HYPOTHESIS", "UNKNOWN"}

@dataclass
class Claim:
    type: str
    subject: str
    metric: str
    value: object
    source_refs: list[str]
    certainty: str

@dataclass
class ActionClaim:
    action_type: str
    resource: str
    requested_parameters: dict
    status: str
    receipt_ref: str | None = None

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

@dataclass(frozen=True)
class TaskContext:
    scenario_id: str
    user_request: str
    initial_state: dict
    available_tools: tuple[str, ...]
    tools: object

class Agent(Protocol):
    version: str
    def apply(self, task_context: TaskContext) -> AgentResult: ...

def validate_result(data):
    # Round-trip JSON is validated before evaluator consumes any agent output.
    result = AgentResult(**data)
    for key in ("final_answer", "decision_summary", "approval_state", "outcome"):
        if not isinstance(getattr(result, key), str):
            raise ValueError("Invalid result string")
    if not isinstance(result.metadata, dict) or not isinstance(result.tool_calls, list):
        raise ValueError("Invalid result containers")
    if not isinstance(result.evidence, list) or not isinstance(result.actions, list):
        raise ValueError("Invalid result lists")
    for item in result.evidence:
        claim = Claim(**item)
        if claim.certainty not in CERTAINTIES or claim.type not in {"metric", "hypothesis", "unknown"}:
            raise ValueError("Invalid typed claim")
        if not all(isinstance(v, str) for v in (claim.subject, claim.metric)) or not isinstance(claim.source_refs, list) or not all(isinstance(v, str) for v in claim.source_refs):
            raise ValueError("Invalid claim fields")
    for item in result.actions:
        action = ActionClaim(**item)
        if action.status not in {"PROPOSED", "ACCEPTED", "EXECUTED", "VERIFIED", "FAILED"}:
            raise ValueError("Invalid action status")
        if action.receipt_ref is not None and not isinstance(action.receipt_ref, str):
            raise ValueError("Invalid receipt reference")
        if not isinstance(action.requested_parameters, dict) or not all(isinstance(v, str) for v in (action.action_type, action.resource)):
            raise ValueError("Invalid action fields")
    return result
