from copy import deepcopy

class InMemoryActionLedger:
    """Supervisor-owned across episodes in ONE evaluation, not durable on disk."""
    def __init__(self):
        self.entries = {}
        self.consumed_approvals = {}

    def lookup(self, workflow, action, resource, key):
        return deepcopy(self.entries.get((workflow, action, resource, key)))

    def record(self, workflow, action, resource, key, parameters, receipt):
        identity = (workflow, action, resource, key)
        if identity in self.entries:
            raise ValueError("Duplicate ledger commit")
        self.entries[identity] = {"parameters": deepcopy(parameters), "receipt": deepcopy(receipt)}

    def for_workflow(self, workflow):
        return [deepcopy(v["receipt"]) for k, v in self.entries.items() if k[0] == workflow]

    def approval_available(self, approval_id, identity, reusable=False):
        return reusable or approval_id not in self.consumed_approvals or self.consumed_approvals[approval_id] == identity

    def consume_approval(self, approval_id, identity, reusable=False):
        if not reusable and approval_id != "not_required":
            if not self.approval_available(approval_id, identity):
                raise ValueError("Approval already consumed")
            self.consumed_approvals[approval_id] = identity

    def update_receipt(self, receipt_id, status):
        for entry in self.entries.values():
            if entry["receipt"]["receipt_id"] == receipt_id:
                entry["receipt"]["status"] = status
                return
        raise ValueError("Unknown receipt")
