from dataclasses import dataclass
import hashlib
import json

def parameters_hash(parameters):
    return hashlib.sha256(json.dumps(parameters, sort_keys=True, allow_nan=False).encode()).hexdigest()

@dataclass(frozen=True)
class Approval:
    approval_id: str
    action_type: str
    resource_id: str
    parameters_hash: str
    issued_at: int
    valid_until: int

    def permits(self, action_type, resource, parameters, now):
        return (self.action_type == action_type and self.resource_id == resource
                and self.parameters_hash == parameters_hash(parameters)
                and self.issued_at <= now < self.valid_until)

class ApprovalPolicy:
    def __init__(self, required, approvals, now):
        self.required, self.now = required, now
        self.approvals = [Approval(**a) for a in approvals]

    def authorize(self, action, resource, parameters, approval_id=None):
        if not self.required:
            return "not_required"
        return next((a.approval_id for a in self.approvals
                     if (approval_id is None or a.approval_id == approval_id)
                     and a.permits(action, resource, parameters, self.now)), None)
