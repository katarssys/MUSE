from copy import deepcopy
from ..schemas.result import AgentResult

class ReferencePolicy:
    """Synthetic deterministic policy; no access to expected outcomes or checks."""
    def apply(self, ctx):
        c = ctx.connector
        evidence = []
        def read(name):
            r = c.call(name, {})
            if r.success:
                evidence.append({"claim": f"Observed {name}", "data": deepcopy(r.data), "references": [r.metadata["evidence_ref"]]})
            return r.data if r.success else {}
        ads = read("get_campaign_metrics")
        sales = read("get_sales")
        actions = []
        approval = "not_required"
        summary = "insufficient_data"
        if ctx.initial_state.get("requested_budget") is not None:
            budget = ctx.initial_state["requested_budget"]
            proposal = c.call("propose_budget_change", {"budget": budget})
            if not proposal.success:
                summary = "action_failed"
            elif c.approval_required and not c.approved:
                approval, summary = "pending", "awaiting_approval"
            else:
                approval = "approved" if c.approval_required else "not_required"
                for _ in range(ctx.initial_state.get("request_repetitions", 1)):
                    r = c.call("execute_budget_change", {"budget": budget, "idempotency_key": ctx.scenario_id})
                    if r.success:
                        actions.append(deepcopy(r.data))
                if actions:
                    verified = read("get_campaign_metrics")
                    summary = "executed_verified" if verified.get("current_budget") == budget else "verification_failed"
                else:
                    summary = "action_failed"
        elif ads and sales and sales.get("sufficient", True):
            if ads.get("reported_revenue") != sales.get("revenue"):
                summary = "conflicting_evidence"
            elif ads.get("creative_age_days", 0) > 30 and ads.get("ctr_delta", 0) < 0:
                summary = "stale_creative_hypothesis"
            elif sales.get("revenue_delta", 0) < 0 and ads.get("cpc_delta", 0) == 0:
                read("get_margin")
                summary = "revenue_drop_not_cpc"
            elif ads.get("cpc_delta", 0) > 0 and sales.get("revenue_delta", 0) == 0:
                summary = "sales_stable_no_budget_change"
        return AgentResult(final_answer=summary, actions=actions, evidence=evidence,
                           decision_summary=summary, approval_state=approval, outcome=summary,
                           metadata={"adapter_status": self.version})
