"""Small synthetic contract runner; no model or external control integration."""
from dataclasses import dataclass, field
from math import isclose, isfinite
from uuid import uuid4


@dataclass(frozen=True)
class EvidenceField:
    source: str
    field: str
    kind: str
    expected: str | float | bool | None = None

    def __post_init__(self):
        if (not isinstance(self.source, str) or not self.source.strip()
                or not isinstance(self.field, str) or not self.field.strip()
                or self.kind not in ('number', 'string', 'boolean')):
            raise ValueError('Invalid evidence field declaration')
        if self.expected is not None and not self.accepts(self.expected):
            raise ValueError('Expected value must match field type')

    def accepts(self, value):
        if self.kind == 'number':
            return numeric(value)
        if self.kind == 'boolean':
            return type(value) is bool
        return isinstance(value, str) and bool(value.strip())


@dataclass(frozen=True)
class MetricTerm:
    source: str
    field: str
    coefficient: float = 1

    def __post_init__(self):
        if (not isinstance(self.source, str) or not self.source.strip()
                or not isinstance(self.field, str) or not self.field.strip()
                or not numeric(self.coefficient)):
            raise ValueError('Invalid numeric relationship term')


@dataclass(frozen=True)
class MetricComparison:
    """Assert left equals a declared weighted sum, with compatible dimensions.

    Dimensions (e.g. units, period, basis) must exist and match on every source.
    A basis conversion is explicit in the terms and field expectations, never
    inferred from metric names. No values are rewritten or synthesized.
    """
    left: MetricTerm
    right: tuple[MetricTerm, ...]
    compatible_fields: tuple[str, ...] = ()
    tolerance: float = 0

    def __post_init__(self):
        if (not isinstance(self.left, MetricTerm) or self.left.coefficient != 1
                or not isinstance(self.right, tuple) or not self.right
                or any(not isinstance(t, MetricTerm) for t in self.right)
                or not numeric(self.tolerance) or self.tolerance < 0
                or not isinstance(self.compatible_fields, tuple)
                or any(not isinstance(f, str) or not f.strip() for f in self.compatible_fields)):
            raise ValueError('Invalid numeric comparison')


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
    evidence_fields: tuple[EvidenceField, ...] = ()
    comparisons: tuple[MetricComparison, ...] = ()

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
        if (not isinstance(self.evidence_fields, tuple)
                or any(not isinstance(f, EvidenceField) or f.source not in self.evidence_sources
                       for f in self.evidence_fields)):
            raise ValueError('Fields must reference required evidence sources')
        fields = {(f.source, f.field): f for f in self.evidence_fields}
        if len(fields) != len(self.evidence_fields):
            raise ValueError('Duplicate evidence field')
        if not isinstance(self.comparisons, tuple):
            raise ValueError('Comparisons must be a tuple')
        for rule in self.comparisons:
            if not isinstance(rule, MetricComparison):
                raise ValueError('Invalid comparison declaration')
            for term in (rule.left, *rule.right):
                spec = fields.get((term.source, term.field))
                if spec is None or spec.kind != 'number':
                    raise ValueError('Comparison terms require declared numeric fields')
                if any((term.source, name) not in fields for name in rule.compatible_fields):
                    raise ValueError('Comparison dimensions require declared fields')


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
    data: dict = field(default_factory=dict)


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
        assessment = self.assess(request.resource, evidence)
        if assessment.status != 'evidence_sufficient':
            return assessment
        previous = self._operations.get(request.key)
        if previous is not None:
            if previous.request != request:
                return Verdict('idempotency_conflict')
            return self.verify(previous)
        receipt = Receipt(uuid4().hex, request)
        self._operations[request.key] = receipt
        self.side_effect_count += 1
        return Verdict('accepted', ('Authoritative readback pending',), receipt)

    def assess(self, resource, evidence):
        """Read-only evidence assessment; never authorizes or submits an action."""
        c = self.contract
        # Last observation for each capability wins; a later negative cannot be hidden.
        latest = {e.source: e for e in evidence if e.resource == resource}
        missing = tuple(s for s in c.evidence_sources
                        if s not in latest or latest[s].sufficient is not True)
        if missing:
            return Verdict('insufficient_evidence', missing)
        for spec in c.evidence_fields:
            data = latest[spec.source].data
            if not isinstance(data, dict) or spec.field not in data or not spec.accepts(data[spec.field]):
                return Verdict('insufficient_evidence', (f'{spec.source}.{spec.field}',))
            if spec.expected is not None and data[spec.field] != spec.expected:
                return Verdict('evidence_conflict', (f'{spec.source}.{spec.field}',))
        for rule in c.comparisons:
            terms = (rule.left, *rule.right)
            base = latest[rule.left.source].data
            for name in rule.compatible_fields:
                if any(type(latest[t.source].data[name]) is not type(base[name])
                       or latest[t.source].data[name] != base[name] for t in terms):
                    return Verdict('evidence_conflict', (f'Incompatible {name}',))
            left = base[rule.left.field]
            right = sum(latest[t.source].data[t.field] * t.coefficient for t in rule.right)
            if not numeric(right) or not isclose(left, right, rel_tol=0, abs_tol=rule.tolerance):
                return Verdict('evidence_conflict', ('Declared numeric relationship not satisfied',))
        return Verdict('evidence_sufficient')

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
