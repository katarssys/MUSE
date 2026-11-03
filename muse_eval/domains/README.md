# Synthetic domain proofs

One `DomainContract` and one `SyntheticWorkflow` implement all five demonstrations.
There is no dispatch on domain names, metric names or benchmark scenario IDs.
This standalone proof does not change or run the frozen evaluator or the P1 model
prompts, parser, provider, loop, orchestration or live benchmark.

## Implemented synthetic proofs

| Domain | Declarative evidence and operation | Demonstrated behavior |
| --- | --- | --- |
| DevOps | Release validation, deployment plan; deploy version; health readback | Unhealthy deployment is not verified; wrong approval scope and duplicate operations are rejected |
| Mechanical Engineering | Vibration, digital twin, inspection; RPM envelope; sensor readback | Missing inspection retains uncertainty; out-of-envelope readback fails verification |
| Inventory generic extension proof | Stock audit; restock quantity; availability readback | An independent third contract uses the same engine without modification |
| Marketing | Campaign metrics and sales report; exact budget change; campaign readback | CPC spike without downstream data cannot authorize a budget action; gross/net comparison requires declared reconciliation and compatible dimensions; budget approval/readback are exact |
| E-commerce | Inventory snapshot, pending orders, supplier state; restock quantity; fulfillment readback | Duplicate reorder has one side effect; changed SKU/quantity conflicts; missing/stale/conflicting evidence blocks action; accepted restock is not fulfilled until correlated readback |

`devops.py`, `mechanical.py`, `marketing.py` and `ecommerce.py` contain domain
**declarations**, not separate engines. Inventory is declared in regression tests.
The original Agent B `test_domains.py` remains unchanged.

## Generic concepts

- Requests bind one action, parameter, exact resource and idempotency key. Approvals
  bind resource/action/parameter/value (including exact value type).
- Required evidence capabilities must be present for the same exact resource and
  explicitly sufficient. The latest observation for a capability wins, including a
  later insufficient observation. Staleness is represented by `sufficient=False`;
  the engine does not infer source freshness or authenticity.
- Optional `EvidenceField(source, field, kind, expected=None)` declarations require
  finite numbers (excluding booleans), nonempty strings or booleans. Optional
  expected values describe allowed basis/status labels. Missing or ill-typed data
  gives `insufficient_evidence`; unexpected declared labels give `evidence_conflict`.
- Optional `MetricComparison` asserts a numeric field equals a declared weighted
  sum of `MetricTerm` fields. Every term must reference a declared numeric field.
  Declared compatibility fields must be present and match in type/value across all
  participating sources. Tolerance is explicit, absolute and defaults to zero;
  there is no implicit relative tolerance, currency conversion or normalization.
- `assess(resource, evidence)` is read-only and returns `evidence_sufficient`,
  `insufficient_evidence` or `evidence_conflict`, retaining uncertainty on failure.
  `evidence_sufficient` means the declared evidence checks passed, not that an
  action happened or a business/physical outcome was proven. `submit` uses this
  same assessment before creating a synthetic side effect.
- Accepted receipts retain the entire request. Same key/payload returns the same
  receipt/current verification without another side effect; changed payload
  conflicts. Original approval/evidence gates also apply to replays.
- Readbacks bind declared path, exact resource and known receipt. The latest state
  must match requested parameter/type, terminal status and optional operating
  envelope. No observation remains `accepted`; an observed pending, failed,
  incomplete or mismatched state is `verification_failed`, never `verified`.

All additions have empty/default declarations so original contracts keep their
behavior. Readback terminal labels already differ by declaration (`healthy`,
`normal`, `available`, `applied`, `fulfilled`); no new domain-specific semantics
are needed in the engine.

## Domain-specific data declarations

Marketing explicitly declares campaign revenue as gross and sales revenue as net.
Its synthetic reconciliation is `sales net = ads gross - sales discounts - sales
refunds`, with equal currency, unit, period and attribution/resource scope. This
formula is a demonstration assumption, not a claim that real Ads and sales systems
always reconcile this way. A direct comparison additionally requires equal basis;
even equal numbers with gross/net labels then conflict. Missing adjustments or
incompatible dimensions remain insufficient/conflicting; the engine never invents
sales impact from CPC or rewrites evidence.

E-commerce declares `available = on_hand - reserved - pending_orders` and requires
a ready supplier. Snapshot/order unit, period and scope must match. These are
explicit synthetic availability assumptions, not universal warehouse accounting.
Approval and fulfillment readback bind the exact SKU and requested quantity; an
acknowledgment alone establishes neither fulfillment nor replenished stock.

The numeric relationship subset expresses these proofs without a limitation that
requires domain branching. It intentionally supports linear equalities, not an
arbitrary formula language, automatic FX conversion, causal reasoning, per-field
freshness policy or production accounting. Arithmetic uses Python finite numeric
values, not a production financial decimal/rounding specification. Each contract
supports one action/parameter/readback path; this is not a multi-action planner.

## Not implemented

- Real Meta Ads API, real sales/commerce platform (Shopify, Kaspi, ERP, payments),
  supplier or warehouse integrations.
- Kubernetes/cloud deployment or real infrastructure control.
- PLC/SCADA/sensors or authenticated engineering observations.
- Production IAM, authenticated approvals, approval expiry/consumption.
- Durable/concurrent ledger, transactional side effects, recovery after crashes.
- Real physical safety guarantees or production readiness.

Observations, sufficiency flags, approvals and readbacks are trusted synthetic
inputs. Only an in-memory side-effect counter changes. A passing test is not a live
integration, business uplift claim or a guarantee of safe real equipment operation.

## Validation

Run from repository root:

```bash
python -m unittest discover -s muse_eval/tests -v
git diff --check
```

`test_marketing_ecommerce.py` covers MK1–MK3, EC1–EC3, negative dimension/type/scope
and correlation cases, explicit tolerance, and all five contracts with opaque
names through the same engine. It also compares the original 156-test files and
P1 core bytes with the accepted starting state. Original frozen/P1 integrity tests
continue to run unchanged.
