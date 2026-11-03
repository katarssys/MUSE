"""Small synthetic contract runner; no model or external control integration."""
from dataclasses import dataclass
from math import isfinite
from uuid import uuid4


@dataclass(frozen=True)
class DomainContract:
    name: str
    action: str
    parameter: str
    evidence_sources: tuple[str, ...]
    readback_path: str
    success_field: str
    success_value: str
    envelope: tuple[float, float] | None = None
    approval_required: bool = True

    def __post_init__(self):
        for value in (self.name, self.action, self.parameter, self.readback_path,
                      self.success_field, self.success_value):
            if not isinstance(value, str) or not value.strip():
                raise ValueError('Contract names and paths must be nonempty strings')
        if (not isinstance(self.evidence_sources, tuple) or not self.evidence_sources
                or any(not isinstance(s, str) or not s.strip() for s in self.evidence_sources)
                or len(set(self.evidence_sources)) != len(self.evidence_sources)):
            raise ValueError('Distinct required evidence capabilities are required')
        if type(self.approval_required) is not bool:
            raise ValueError('approval_required must be boolean')
        if self.envelope is not None:
            if (len(self.envelope) != 2 or any(not numeric(x) for x in self.envelope)
                    or self.envelope[0] > self.envelope[1]):
                raise ValueError('Invalid operating envelope')


def numeric(value):
    return type(value) in (int, float) and isfinite(value)


@dataclass(frozen=True)
class Request:
    resource: str
    action: str
    parameter: str
    value: str | float
    key: str

    def __post_init__(self):
        if any(not isinstance(v, str) or not v.strip()
               for v in (self.resource, self.action, self.parameter, self.key)):
            raise ValueError('Request identity must be nonempty')
        if not (isinstance(self.value, str) and self.value.strip()) and not numeric(self.value):
            raise ValueError('Request value must be a finite number or nonempty string')


@dataclass(frozen=True)
class Approval:
    resource: str
    action: str
    parameter: str
    value: str | float

    def permits(self, request):
        return (self.resource, self.action, self.parameter) == (
            request.resource, request.action, request.parameter
        ) and type(self.value) is type(request.value) and self.value == request.value


@dataclass(frozen=True)
class Evidence:
    source: str
    resource: str
    sufficient: bool


@dataclass(frozen=True)
class Receipt:
    id: str
    request: Request
    status: str = 'accepted'


@dataclass
class Verdict:
    status: str
    uncertainty: tuple[str, ...] = ()
    receipt: Receipt | None = None


class SyntheticWorkflow:
    """Sequential in-memory proof. Inputs represent trusted synthetic observations.

    Scope is the exact resource string (include cluster/tenant when applicable).
    Latest readback is authoritative. Receipts alone never establish success.
    """

    def __init__(self, contract):
        self.contract = contract
        self._operations = {}
        self._observations = {}
        self.side_effect_count = 0

    def submit(self, request, evidence, approval=None):
        c = self.contract
        if (request.action, request.parameter) != (c.action, c.parameter):
            return Verdict('scope_rejected')
        if c.envelope is not None and (
                not numeric(request.value) or not c.envelope[0] <= request.value <= c.envelope[1]):
            return Verdict('constraint_rejected')
        if c.approval_required and (approval is None or not approval.permits(request)):
            return Verdict('approval_required', ('Exact scoped approval missing',))
        # Last observation for each capability wins; a later negative cannot be hidden.
        latest = {e.source: e for e in evidence if e.resource == request.resource}
        missing = tuple(s for s in c.evidence_sources
                        if s not in latest or latest[s].sufficient is not True)
        if missing:
            return Verdict('insufficient_evidence', missing)
        previous = self._operations.get(request.key)
        if previous is not None:
            if previous.request != request:
                return Verdict('idempotency_conflict')
            return self.verify(previous)
        receipt = Receipt(uuid4().hex, request)
        self._operations[request.key] = receipt
        self.side_effect_count += 1
        return Verdict('accepted', ('Authoritative readback pending',), receipt)

    def observe(self, path, resource, receipt_id, state):
        """Record a copied synthetic readback, correlated to a known operation."""
        receipt = next((r for r in self._operations.values() if r.id == receipt_id), None)
        if (path != self.contract.readback_path or receipt is None
                or resource != receipt.request.resource):
            raise ValueError('Readback scope/path/receipt mismatch')
        self._observations[receipt_id] = dict(state)

    def verify(self, receipt):
        if self._operations.get(receipt.request.key) != receipt:
            raise ValueError('Unknown receipt')
        state = self._observations.get(receipt.id)
        if state is None:
            return Verdict('accepted', ('Authoritative readback pending',), receipt)
        c = self.contract
        value = state.get(c.parameter)
        matches = type(value) is type(receipt.request.value) and value == receipt.request.value
        safe = c.envelope is None or (numeric(value) and c.envelope[0] <= value <= c.envelope[1])
        success = state.get(c.success_field) == c.success_value and matches and safe
        return Verdict('verified' if success else 'verification_failed',
                       () if success else ('Readback does not establish requested safe state',), receipt)
