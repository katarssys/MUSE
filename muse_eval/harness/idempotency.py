from copy import deepcopy

class InMemoryActionLedger:
    """Supervisor-owned across episodes in ONE evaluation, not durable on disk."""
    def __init__(self):
        self.entries = {}

    def lookup(self, workflow, action, resource, key):
        return deepcopy(self.entries.get((workflow, action, resource, key)))

    def record(self, workflow, action, resource, key, parameters, receipt):
        identity = (workflow, action, resource, key)
        if identity in self.entries:
            raise ValueError("Duplicate ledger commit")
        self.entries[identity] = {"parameters": deepcopy(parameters), "receipt": deepcopy(receipt)}

    def for_workflow(self, workflow):
        return [deepcopy(v["receipt"]) for k, v in self.entries.items() if k[0] == workflow]
