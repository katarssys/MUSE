from copy import deepcopy
from dataclasses import asdict
from time import perf_counter
from .base import ToolResult

READ_TOOLS = {"get_campaign_metrics", "get_sales", "get_margin", "get_leads", "get_attribution"}

class MockConnector:
    """Run-local ledger. Approval is trusted fixture state, never caller input."""
    def __init__(self, scenario, telemetry):
        self.fixtures = deepcopy(scenario.fixture_data)
        self.allowed = set(scenario.available_tools)
        self.forbidden = set(scenario.forbidden_actions)
        self.approval_required = scenario.approval_required
        self.approved = scenario.initial_state.get("approval_granted", False) is True
        self.telemetry = telemetry
        self.events = []
        self.receipts = {}
        self.budget = scenario.initial_state.get("budget", 100)

    def call(self, name, args):
        start = perf_counter()
        args = deepcopy(args)
        result = self._dispatch(name, args)
        elapsed = (perf_counter() - start) * 1000
        self.telemetry.tool_time_ms += elapsed
        self.telemetry.tool_call_count += 1
        result.metadata["evidence_ref"] = f"tool:{len(self.events)+1}"
        self.events.append({"selected_tool": name, "tool_args": args,
                            "tool_result": asdict(result), "latency_ms": elapsed})
        return result

    def _dispatch(self, name, args):
        if name not in self.allowed or name in self.forbidden:
            return ToolResult(False, error="tool_not_allowed")
        if name in READ_TOOLS:
            data = deepcopy(self.fixtures.get(name))
            if data is None:
                return ToolResult(False, error="missing_fixture")
            if name == "get_campaign_metrics":
                data["current_budget"] = self.budget
                data["receipts"] = deepcopy(list(self.receipts.values()))
            return ToolResult(True, data)
        if name == "propose_budget_change":
            return ToolResult(True, {"status": "proposed", "budget": args.get("budget")})
        if name == "execute_budget_change":
            if self.approval_required and not self.approved:
                return ToolResult(False, error="approval_required")
            key, budget = args.get("idempotency_key"), args.get("budget")
            if not isinstance(key, str) or not key or type(budget) not in (int, float) or not 0 < budget < 1e9:
                return ToolResult(False, error="invalid_action")
            if key in self.receipts:
                old = self.receipts[key]
                if old["budget"] != budget:
                    return ToolResult(False, error="idempotency_conflict")
                return ToolResult(True, deepcopy(old), metadata={"replayed": True})
            if self.fixtures.get("execution_failure"):
                return ToolResult(False, error="synthetic_execution_failure")
            receipt = {"execution_id": f"exec-{len(self.receipts)+1}",
                       "idempotency_key": key, "budget": budget, "status": "executed"}
            self.receipts[key] = receipt
            self.budget = budget
            return ToolResult(True, deepcopy(receipt), metadata={"replayed": False})
        return ToolResult(False, error="unknown_tool")
