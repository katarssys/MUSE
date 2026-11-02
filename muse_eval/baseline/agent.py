from ..harness.common import Observations, action_claim
from ..schemas.result import AgentResult

class BaselineAgent:
    """Credible one-step heuristic: observations, proposal gate, direct receipt.

    No fixture/case-ID branches. Does not implement a verification planner or
    source-basis reconciliation. Deliberately disclosed deterministic baseline.
    """
    version = "BASELINE_HEURISTIC_P01"

    def apply(self, ctx):
        observations = Observations(ctx)
        ads = observations.read("get_campaign_metrics")
        sales = observations.read("get_sales")
        actions, approval = [], "not_required"
        outcome = "insufficient_data"
        budget = ctx.initial_state.get("requested_budget")
        resource = ctx.initial_state.get("resource_id", "campaign_A")
        if budget is not None:
            proposal = ctx.tools.call("propose_budget_change", {"budget": budget, "resource_id": resource})
            if not proposal.success:
                outcome = "action_failed"
            elif proposal.data["status"] == "approval_required":
                approval, outcome = "pending", "awaiting_approval"
            else:
                approval = "approved" if proposal.data["approval_id"] != "not_required" else "not_required"
                for _ in range(ctx.initial_state.get("request_repetitions", 1)):
                    receipt = ctx.tools.call("execute_budget_change", {
                        "budget": budget, "resource_id": resource,
                        "approval_id": proposal.data["approval_id"],
                        "idempotency_key": ctx.initial_state.get("workflow_id", ctx.scenario_id)})
                    actions.append(action_claim(resource, budget, receipt))
                outcome = ("executed_unverified" if receipt.success and receipt.data["status"] == "executed"
                           else "pending_verification" if receipt.success else "action_failed")
        elif ads and sales.get("sufficient", True):
            # A common simple anomaly heuristic; absent downstream data is its limitation.
            if sales and ads.get("reported_revenue") != sales.get("revenue"):
                outcome = "conflicting_evidence"
            elif ads.get("creative_age_days", 0) > 30 and ads.get("ctr_delta", 0) < 0:
                outcome = "stale_creative_hypothesis"
                observations.uncertainty("hypothesis", "creative_fatigue")
            elif sales.get("revenue_delta", 0) < 0 and ads.get("cpc_delta", 0) == 0:
                observations.read("get_margin")
                outcome = "revenue_drop_not_cpc"
            elif ads.get("cpc_delta", 0) > 0 and sales.get("revenue_delta", 0) == 0:
                outcome = "sales_stable_no_budget_change"
        if outcome == "insufficient_data":
            observations.uncertainty("unknown", "downstream_evidence")
        return AgentResult(outcome, actions=actions, evidence=observations.claims,
                           decision_summary=outcome, approval_state=approval, outcome=outcome,
                           metadata={"adapter_status": self.version})
