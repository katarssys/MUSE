"""Shared observation/action formatting, never evaluator expectations."""
from dataclasses import asdict
from ..schemas.result import Claim, ActionClaim

class Observations:
    def __init__(self, context):
        self.context = context
        self.claims = []

    def read(self, name):
        result = self.context.tools.call(name, {})
        if result.success:
            ref = result.metadata["evidence_ref"]
            for metric, value in result.data.items():
                if type(value) in (int, float, str, bool):
                    self.claims.append(asdict(Claim("metric", name, metric, value, [ref], "FACT")))
            return result.data
        return {}

    def uncertainty(self, kind, metric, value=None):
        refs = list(dict.fromkeys(ref for c in self.claims for ref in c["source_refs"]))
        self.claims.append(asdict(Claim(kind, "campaign", metric, value, refs,
                                       "HYPOTHESIS" if kind == "hypothesis" else "UNKNOWN")))

def action_claim(resource, budget, result, status=None):
    state = status or (result.data.get("status", "failed").upper() if result.success else "FAILED")
    return asdict(ActionClaim("execute_budget_change", resource, {"budget": budget},
                              state, result.data.get("receipt_id")))

class ReferencePolicy:
    """Compatibility infrastructure policy; not the comparison baseline."""
    version = "INFRASTRUCTURE_REFERENCE"
    def apply(self, context):
        from ..candidate.agent import CandidateAgent
        return CandidateAgent().apply(context)
