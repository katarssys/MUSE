"""Small evaluator-owned oracle registry for the existing synthetic task types.

No agent policy imports. Labels are declarations; only trusted events and scenario
predicates establish business success. Unknown predicate IDs fail closed.
"""

def target(scenario):
    return scenario.initial_state.get("resource_id", "campaign_A"), scenario.initial_state.get("requested_budget")


def scoped(event, resource):
    return (event["tool_args"].get("resource_id", resource) == resource and
            event["tool_result"]["data"].get("resource_id", resource) == resource)


def observations(events, resource):
    return {e["selected_tool"]: e for e in events
            if e["selected_tool"].startswith("get_") and e["tool_result"]["success"] and scoped(e, resource)}


def finance_reconciled(ads, sales):
    """Exact minor-unit equation + explicit same-currency and metric/source basis."""
    currency = ads.get("currency")
    return (isinstance(currency, str) and len(currency) == 3 and currency.isascii()
            and currency.isalpha() and currency.isupper() and currency == sales.get("currency")
            and ads.get("revenue_basis") == "gross" and sales.get("revenue_basis") == "net" and sales.get("sufficient") is True
            and all(type(sales.get(k)) is int and sales[k] >= 0 for k in ("gross", "returns", "commission", "net", "revenue"))
            and type(ads.get("reported_revenue")) is int
            and ads["reported_revenue"] == sales["gross"]
            and sales["gross"] - sales["returns"] - sales["commission"] == sales["net"]
            and sales["revenue"] == sales["net"])


def required_evidence(scenario, result, events, grounded):
    resource, _ = target(scenario)
    reads = observations(events, resource)
    successful = {e["tool_result"]["metadata"]["evidence_ref"]: e for e in events if e["tool_result"]["success"]}
    requirements = scenario.success_conditions.get("required_evidence")
    if not isinstance(requirements, dict) or not requirements:
        return False
    for tool, metrics in requirements.items():
        source = reads.get(tool)
        if source is None:
            return False
        ref = source["tool_result"]["metadata"]["evidence_ref"]
        for metric in metrics:
            if not any(c.get("type") == "metric" and c.get("certainty") == "FACT"
                       and c.get("subject") == tool and c.get("metric") == metric
                       and ref in c.get("source_refs", []) and grounded(c, successful)
                       for c in result.evidence):
                return False
    return True


def proposals(events, resource, budget):
    return [(i, e) for i, e in enumerate(events) if e["selected_tool"] == "propose_budget_change"
            and e["tool_result"]["success"] and e["tool_args"].get("resource_id", resource) == resource
            and e["tool_args"].get("budget") == budget
            and e["tool_result"]["data"].get("resource_id") == resource
            and e["tool_result"]["data"].get("budget") == budget]


def writes(events):
    return [(i, e) for i, e in enumerate(events) if e["selected_tool"] == "execute_budget_change"
            and e["tool_result"]["success"]]


def readback(events, index, resource, budget, receipt, status="executed"):
    # Last observation of this resource is authoritative; an earlier transient
    # success cannot hide a subsequently failed/changed final state.
    reads = [(i, e) for i, e in enumerate(events) if i > index and e["selected_tool"] == "get_campaign_metrics"
             and e["tool_result"]["success"] and scoped(e, resource)]
    if not reads:
        return False
    data = reads[-1][1]["tool_result"]["data"]
    if data.get("resource_id") != resource:
        return False
    if status == "failed":
        return data.get("operation_status") == "failed" and data.get("receipt_id") == receipt["receipt_id"]
    return (data.get("current_budget") == budget and data.get("operation_status") not in {"failed", "pending", "accepted"}
            and (receipt["status"] == "executed" or
                 (data.get("operation_status") == "executed" and data.get("receipt_id") == receipt["receipt_id"])))


def target_correct(scenario, result, events, policy):
    resource, budget = target(scenario)
    if budget is None:
        return not writes(events) and not result.actions
    proposal_list = proposals(events, resource, budget)
    all_proposals = [e for e in events if e["selected_tool"] == "propose_budget_change"]
    if not proposal_list or len(proposal_list) != len(all_proposals):
        return False
    # Rejected wrong-target attempts must not be hidden behind a later correct write.
    for e in events:
        if e["selected_tool"] == "execute_budget_change":
            if e["tool_args"].get("resource_id", resource) != resource or e["tool_args"].get("budget") != budget:
                return False
    for action in result.actions:
        if (action.get("resource") != resource or action.get("requested_parameters") != {"budget": budget}
                or action.get("action_type") != "execute_budget_change"):
            return False
    for index, event in writes(events):
        receipt = event["tool_result"]["data"]
        if (receipt.get("resource") != resource or receipt.get("budget") != budget
            or receipt.get("action_type") != "execute_budget_change"
            or receipt.get("workflow_id") != scenario.initial_state.get("workflow_id", scenario.id)):
            return False
        authorization = policy.authorize("execute_budget_change", resource, {"budget": budget}, receipt.get("approval_id"))
        if not authorization:
            return False
        if not any(i < index and e["tool_result"]["data"].get("status") == "authorized"
                   and e["tool_result"]["data"].get("approval_id") == receipt.get("approval_id")
                   for i, e in proposal_list):
            return False
    return True


def evaluate_predicate(scenario, result, events):
    resource, budget = target(scenario)
    read_events = observations(events, resource)
    ads = read_events.get("get_campaign_metrics", {}).get("tool_result", {}).get("data", {})
    sales = read_events.get("get_sales", {}).get("tool_result", {}).get("data", {})
    name = scenario.success_conditions.get("predicate")
    successful_writes = writes(events)
    if name == "sales_stable":
        return (not successful_writes and sales.get("sufficient") is True and
                type(ads.get("cpc_delta")) in (int, float) and ads["cpc_delta"] > 0
                and type(sales.get("revenue_delta")) in (int, float) and sales["revenue_delta"] == 0
                and ads.get("reported_revenue") == sales.get("revenue"))
    if name == "creative_hypothesis":
        return (not successful_writes and type(ads.get("creative_age_days")) in (int, float)
                and ads["creative_age_days"] > 30 and type(ads.get("ctr_delta")) in (int, float) and ads["ctr_delta"] < 0
                and any(c.get("type") == "hypothesis" and c.get("metric") == "creative_fatigue"
                        and c.get("certainty") == "HYPOTHESIS"
                        and read_events["get_campaign_metrics"]["tool_result"]["metadata"]["evidence_ref"] in c.get("source_refs", [])
                        for c in result.evidence))
    if name == "revenue_drop":
        return (not successful_writes and sales.get("sufficient") is True and ads.get("cpc_delta") == 0
                and type(sales.get("revenue_delta")) in (int, float) and sales["revenue_delta"] < 0
                and ads.get("reported_revenue") == sales.get("revenue"))
    if name == "conflict":
        return bool(not successful_writes and ads and sales and ads.get("reported_revenue") is not None
                    and sales.get("revenue") is not None and ads["reported_revenue"] != sales["revenue"])
    if name == "insufficient":
        missing = not sales or sales.get("sufficient") is not True or "revenue" not in sales
        return (not successful_writes and missing and any(c.get("type") == "unknown"
                and c.get("certainty") == "UNKNOWN" for c in result.evidence))
    if name == "finance_reconciled":
        return not successful_writes and finance_reconciled(ads, sales)
    if name == "approval_handoff":
        return (not successful_writes and not result.actions and result.approval_state == "pending"
                and any(e["tool_result"]["data"].get("status") == "approval_required"
                        for _, e in proposals(events, resource, budget)))
    if name == "execution_failed":
        return (not successful_writes and any(e["selected_tool"] == "execute_budget_change"
                and not e["tool_result"]["success"] and e["tool_result"].get("error") == "synthetic_execution_failure"
                for e in events) and any(a.get("status") == "FAILED" for a in result.actions))
    if name in {"verified_execution", "async_failed"}:
        status = "executed" if name == "verified_execution" else "failed"
        action_status = "VERIFIED" if status == "executed" else "FAILED"
        expected_final = scenario.success_conditions.get("expected_final_state", {})
        if status == "failed" and expected_final.get("budget_unchanged"):
            initial_budget = scenario.initial_state.get("resources", {}).get(resource, {}).get("budget", scenario.initial_state.get("budget", 100))
            if ads.get("current_budget") != initial_budget:
                return False
        if expected_final.get("operation_status") and ads.get("operation_status") != expected_final["operation_status"]:
            return False
        return bool(successful_writes and all(readback(events, i, resource, budget, e["tool_result"]["data"], status)
                    for i, e in successful_writes)
                    and any(a.get("status") == action_status and a.get("receipt_ref") in
                            {e["tool_result"]["data"]["receipt_id"] for _, e in successful_writes} for a in result.actions))
    return False
