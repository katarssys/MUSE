from ..harness.common import Observations, action_claim
from ..schemas.result import AgentResult

class CandidateAgent:
    """Deterministic evidence-aware planner, not production MUSE or an LLM."""
    version = "CANDIDATE_PLANNER_P02"

    def apply(self, ctx):
        observations = Observations(ctx)
        ads = observations.read("get_campaign_metrics")
        sales = observations.read("get_sales")
        actions, approval = [], "not_required"
        outcome = "insufficient_data"
        resource = ctx.initial_state.get("resource_id", "campaign_A")
        budget = ctx.initial_state.get("requested_budget")
        if budget is not None:
            proposal = ctx.tools.call("propose_budget_change", {"budget": budget, "resource_id": resource, "idempotency_key": ctx.initial_state.get("workflow_id", ctx.scenario_id)})
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
                if not receipt.success:
                    outcome = "action_failed"
                else:
                    final = observations.read("get_campaign_metrics")
                    if final.get("operation_status") == "failed":
                        actions[-1]["status"] = "FAILED"
                        outcome = "verification_failed"
                    elif (final.get("resource_id") == resource and final.get("current_budget") == budget
                          and (receipt.data["status"] == "executed" or final.get("operation_status") == "executed")):
                        actions[-1]["status"] = "VERIFIED"
                        outcome = "executed_verified"
                    else:
                        outcome = "pending_verification"
        elif ads and sales and sales.get("sufficient", True) and "revenue" in sales:
            ads_basis, sales_basis = ads.get("revenue_basis"), sales.get("revenue_basis")
            if ads_basis and sales_basis and ads_basis != sales_basis:
                # Reconcile only same-unit observed values; no currency conversions or inferred net.
                if (ads_basis == "gross" and sales_basis == "net" and
                    isinstance(ads.get("currency"), str) and len(ads["currency"]) == 3 and
                    ads["currency"].isupper() and ads.get("currency") == sales.get("currency") and
                    ads.get("reported_revenue") == sales.get("gross") and
                    all(type(sales.get(k)) is int for k in ("gross", "returns", "commission", "net")) and
                    sales["gross"] - sales["returns"] - sales["commission"] == sales["net"] and
                    sales.get("revenue") == sales["net"]):
                    outcome = "revenue_basis_reconciled"
                else:
                    outcome = "conflicting_evidence"
            elif ads.get("reported_revenue") != sales.get("revenue"):
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
