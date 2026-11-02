from copy import deepcopy
from dataclasses import asdict
from time import perf_counter
from .base import ToolResult
from ..harness.policy import ApprovalPolicy
from ..harness.idempotency import InMemoryActionLedger

READ_TOOLS = {"get_campaign_metrics", "get_sales", "get_margin", "get_leads", "get_attribution"}
ACTION = "execute_budget_change"

class MockConnector:
    def __init__(self, scenario, telemetry, ledger=None):
        self.fixtures = deepcopy(scenario.fixture_data)
        self.allowed = set(scenario.available_tools)
        self.forbidden = set(scenario.forbidden_actions)
        self.policy = ApprovalPolicy(scenario.approval_required, self.fixtures.get("approvals", []),
                                     self.fixtures.get("clock", 1000))
        self.telemetry = telemetry
        self.events = []
        self.ledger = ledger if ledger is not None else InMemoryActionLedger()
        self.workflow = scenario.initial_state.get("workflow_id", scenario.id)
        self.resource = scenario.initial_state.get("resource_id", "campaign_A")
        self.budget = scenario.initial_state.get("budget", 100)
        prior = self.ledger.for_workflow(self.workflow)
        for receipt in prior:
            if receipt["resource"] == self.resource and receipt["status"] == "executed":
                self.budget = receipt["budget"]
        self.pending = None
        self.max_calls = scenario.success_conditions.get("tool_budget", 12)

    def call(self, name, args):
        start = perf_counter()
        args = deepcopy(args)
        result = self._dispatch(name, args) if len(self.events) < self.max_calls else ToolResult(False, error="tool_budget_exceeded")
        elapsed = (perf_counter() - start) * 1000
        self.telemetry.tool_time_ms += elapsed
        self.telemetry.tool_call_count += 1
        result.metadata["evidence_ref"] = f"{getattr(self, 'event_prefix', '')}tool:{len(self.events)+1}"
        self.events.append({"selected_tool": name, "tool_args": args,
                            "tool_result": asdict(result), "latency_ms": elapsed})
        return deepcopy(result)

    def _dispatch(self, name, args):
        if name not in self.allowed or name in self.forbidden:
            return ToolResult(False, error="tool_not_allowed")
        if name in READ_TOOLS:
            data = deepcopy(self.fixtures.get(name))
            if data is None:
                return ToolResult(False, error="missing_fixture")
            if name == "get_campaign_metrics":
                data.update(current_budget=self.budget, resource_id=self.resource)
                if self.pending:
                    data["operation_status"] = "failed"
                    data["receipt_id"] = self.pending["receipt_id"]
            return ToolResult(True, data)
        resource = args.get("resource_id", self.resource)
        budget = args.get("budget")
        if type(budget) not in (int, float) or not 0 < budget < 1e9 or not isinstance(resource, str):
            return ToolResult(False, error="invalid_action")
        parameters = {"budget": budget}
        approval_id = self.policy.authorize(ACTION, resource, parameters, args.get("approval_id"))
        if name == "propose_budget_change":
            return ToolResult(True, {"status": "authorized" if approval_id else "approval_required",
                                    "resource_id": resource, "budget": budget, "approval_id": approval_id})
        if name == ACTION:
            if not approval_id:
                return ToolResult(False, error="approval_required")
            key = args.get("idempotency_key")
            if not isinstance(key, str) or not key:
                return ToolResult(False, error="invalid_idempotency_key")
            prior = self.ledger.lookup(self.workflow, ACTION, resource, key)
            if prior:
                if prior["parameters"] != parameters:
                    return ToolResult(False, error="idempotency_conflict")
                if prior["receipt"]["status"] == "executed":
                    self.budget = prior["receipt"]["budget"]
                else:
                    self.pending = prior["receipt"]
                return ToolResult(True, prior["receipt"], metadata={"replayed": True})
            if self.fixtures.get("execution_failure"):
                return ToolResult(False, error="synthetic_execution_failure")
            status = "accepted" if self.fixtures.get("async_failure") else "executed"
            receipt = {"receipt_id": f"{self.workflow}:receipt-{len(self.ledger.entries)+1}",
                       "workflow_id": self.workflow, "action_type": ACTION, "resource": resource,
                       "idempotency_key": key, "budget": budget, "status": status,
                       "approval_id": approval_id}
            self.ledger.record(self.workflow, ACTION, resource, key, parameters, receipt)
            if status == "executed":
                self.budget = budget
            else:
                self.pending = receipt
            return ToolResult(True, receipt, metadata={"replayed": False})
        return ToolResult(False, error="unknown_tool")
