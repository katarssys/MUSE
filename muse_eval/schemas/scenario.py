from dataclasses import dataclass, fields
import json
from pathlib import Path

@dataclass
class Scenario:
    id: str
    domain: str
    user_request: str
    initial_state: dict
    available_tools: list[str]
    fixture_data: dict
    expected_outcome: str
    forbidden_actions: list[str]
    approval_required: bool
    success_conditions: dict

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text())
        types = {"id": str, "domain": str, "user_request": str,
                 "initial_state": dict, "available_tools": list, "fixture_data": dict,
                 "expected_outcome": str, "forbidden_actions": list,
                 "approval_required": bool, "success_conditions": dict}
        if set(data) != {f.name for f in fields(cls)}:
            raise ValueError("Scenario fields do not match schema")
        for key, kind in types.items():
            if type(data[key]) is not kind:
                raise ValueError(f"Invalid type for {key}")
        for key in ("available_tools", "forbidden_actions"):
            if not all(isinstance(v, str) for v in data[key]):
                raise ValueError(f"{key} must contain strings")
        if not data["id"] or not data["user_request"]:
            raise ValueError("Scenario id and request must be nonempty")
        return cls(**data)
