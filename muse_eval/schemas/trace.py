from dataclasses import dataclass, asdict
from datetime import datetime, timezone

SENSITIVE = {"secret", "secrets", "token", "tokens", "password", "credentials", "authorization", "api_key", "private_key"}

def sanitize(value):
    """Structured redaction; free text must never contain credentials or reasoning."""
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if k not in {"input_tokens", "output_tokens", "cached_tokens"} and any(s in k.lower() for s in SENSITIVE) else sanitize(v))
                for k, v in value.items() if k.lower() not in {"chain_of_thought", "private_reasoning"}}
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    return value

@dataclass
class Trace:
    scenario_id: str
    agent_version: str
    timestamp: str
    events: list
    evidence: list
    decision_summary: str
    approval_state: str
    action: list
    verification: dict
    outcome: str
    latency_ms: float
    model_calls: int
    tool_calls_count: int
    estimated_cost: float | None

    def to_dict(self):
        return sanitize(asdict(self))

def timestamp():
    return datetime.now(timezone.utc).isoformat()
