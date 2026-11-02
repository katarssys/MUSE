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
        self.states = deepcopy(scenario.initial_state.get("resources", {}))
        self.states.setdefault(self.resource, {"budget": scenario.initial_state.get("budget", 100)})
        self.pending = {}
        for receipt in self.ledger.for_workflow(self.workflow):
            resource = receipt["resource"]
            if resource not in self.states:
                continue
            if receipt["status"] == "executed":
                self.states[resource]["budget"] = receipt["budget"]
            elif receipt["status"] == "accepted":
                self.pending[resource] = {"receipt": receipt, "step": 0}
        self.max_calls = scenario.success_conditions.get("tool_budget", 12)

    @property
    def budget(self):
        """Compatibility read-only view of the default resource."""
        return self.states[self.resource]["budget"]

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

    def _readback(self, resource, data):
        if resource in self.pending:
            pending = self.pending[resource]
            receipt = pending["receipt"]
            transitions = self.fixtures.get("async_transitions", ["failed"])
            status = transitions[min(pending["step"], len(transitions)-1)]
            pending["step"] += 1
            if status == "executed":
                self.states[resource]["budget"] = receipt["budget"]
            if status in {"executed", "failed"}:
                self.ledger.update_receipt(receipt["receipt_id"], status)
            data.update(operation_status=status, receipt_id=receipt["receipt_id"])
        data.update(current_budget=self.states[resource]["budget"], resource_id=resource)
        return data

    def _dispatch(self, name, args):
        if name not in self.allowed or name in self.forbidden:
            return ToolResult(False, error="tool_not_allowed")
        resource = args.get("resource_id", self.resource)
        if not isinstance(resource, str) or resource not in self.states:
            return ToolResult(False, error="resource_not_found")
        if name in READ_TOOLS:
            resource_fixtures = self.fixtures.get("resources", {}).get(resource, {})
            data = deepcopy(resource_fixtures.get(name, self.fixtures.get(name) if resource == self.resource else None))
            if data is None and name != "get_campaign_metrics":
                return ToolResult(False, error="missing_fixture")
            if name == "get_campaign_metrics":
                # Missing metrics remain missing; state reads never invent another resource's metrics.
                data = self._readback(resource, data or {})
            else:
                data["resource_id"] = resource
            return ToolResult(True, data)
        budget = args.get("budget")
        if type(budget) not in (int, float) or not 0 < budget < 1e9:
            return ToolResult(False, error="invalid_action")
        parameters = {"budget": budget}
        approval_id = self.policy.authorize(ACTION, resource, parameters, args.get("approval_id"))
        key = args.get("idempotency_key")
        identity = (self.workflow, ACTION, resource, key)
        reusable = any(a.approval_id == approval_id and a.reusable for a in self.policy.approvals)
        prior = self.ledger.lookup(*identity) if isinstance(key, str) else None
        # Scope/expiry still apply to replays, but the same committed operation can reuse its approval.
        available = approval_id and (approval_id == "not_required" or reusable or
                     approval_id not in self.ledger.consumed_approvals or
                     (prior and self.ledger.consumed_approvals[approval_id] == identity))
        if name == "propose_budget_change":
            return ToolResult(True, {"status": "authorized" if available else "approval_required",
                                    "resource_id": resource, "budget": budget,
                                    "approval_id": approval_id if available else None})
        if name == ACTION:
            if not isinstance(key, str) or not key:
                return ToolResult(False, error="invalid_idempotency_key")
            if prior and prior["parameters"] != parameters:
                return ToolResult(False, error="idempotency_conflict")
            if not available:
                return ToolResult(False, error="approval_required")
            if prior:
                return ToolResult(True, prior["receipt"], metadata={"replayed": True})
            if self.fixtures.get("execution_failure"):
                return ToolResult(False, error="synthetic_execution_failure")
            status = "accepted" if self.fixtures.get("async_failure") or self.fixtures.get("async_transitions") else "executed"
            receipt = {"receipt_id": f"{self.workflow}:receipt-{len(self.ledger.entries)+1}",
                       "workflow_id": self.workflow, "action_type": ACTION, "resource": resource,
                       "idempotency_key": key, "budget": budget, "status": status, "approval_id": approval_id}
            self.ledger.record(self.workflow, ACTION, resource, key, parameters, receipt)
            self.ledger.consume_approval(approval_id, identity, reusable)
            if status == "executed":
                self.states[resource]["budget"] = budget
            else:
                self.pending[resource] = {"receipt": deepcopy(receipt), "step": 0}
            return ToolResult(True, receipt, metadata={"replayed": False})
        return ToolResult(False, error="unknown_tool")
