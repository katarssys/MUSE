# Codex task: Marketing + E-commerce domain proof

Branch: `codex/muse-domains-marketing-ecommerce`
Base branch: `codex/muse-model-adapter-p1`

## First required step

Before implementation, incorporate the accepted generic domain-contract work from Agent B:

```bash
git fetch origin
git cherry-pick f0cfe9cfc433b10680e9445ab8aecca6ee1e5a1d
```

If the cherry-pick conflicts, stop and report the conflict. Do not hand-rewrite the accepted Agent B implementation.

After cherry-pick, the branch must contain:

- `muse_eval/domains/contract.py`
- `muse_eval/domains/devops.py`
- `muse_eval/domains/mechanical.py`
- `muse_eval/tests/test_domains.py`

The accepted starting state is 156/156 tests passing.

## Goal

Extend the SAME generic domain-contract machinery so that it can support:

1. Marketing
2. E-commerce

without breaking DevOps, Mechanical Engineering, Inventory proof, frozen P0.2,
or the existing green P1 live-model benchmark core.

This is a hackathon universality proof, not a production integration with Meta Ads,
Shopify, Kaspi, ERP, payment processors, or warehouses.

## Non-negotiable constraints

DO NOT modify:

- `muse_eval/harness/**`
- `muse_eval/task/scenarios/**`
- `muse_eval/schemas/**`
- `muse_eval/connectors/**`
- `muse_eval/baseline/**`
- `muse_eval/candidate/**`
- existing five-case live benchmark semantics
- `muse_eval/agents/model/orchestration.py`
- `muse_eval/agents/model/loop.py`
- `muse_eval/agents/model/parser.py`
- existing P1 prompts unless a genuinely domain-neutral addition is required

Do not add scenario IDs, expected outcomes, frozen predicates, fixture-specific logic,
or evaluator answer maps to generic production code.

Do not replace or fork the existing DomainContract into a Marketing-specific engine.

## Architectural objective

The existing Agent B contract already demonstrates:

- exact resource scope
- exact approval scope
- required evidence sources
- idempotency
- accepted != verified
- readback correlation
- final state verification
- optional numeric operating envelope

Marketing and E-commerce need richer declarations, especially:

- typed evidence fields
- cross-source comparison
- metric basis / units / currency compatibility
- simple derived relationships / invariants
- possibly different terminal action semantics

Extend the contract only where these concepts are genuinely generic.

A good design may introduce small declarative concepts such as:

- EvidenceField / MetricSpec
- invariant/comparison rules
- normalization declarations
- source compatibility constraints
- optional action/readback semantics

The core must still not contain:

```python
if domain == "marketing":
    ...
elif domain == "ecommerce":
    ...
```

Likewise, avoid rules like `if metric == "revenue"` in the generic engine if a declarative relationship can express the same requirement.

## Marketing proof

Implement at least THREE deterministic synthetic scenarios/tests.

### MK1 — CPC spike but downstream sales unavailable

Inputs:
- campaign metrics show CPC increase
- sales/downstream evidence is missing or insufficient

Required result:
- no destructive budget action
- explicit insufficient-evidence/uncertainty state
- no fabricated sales impact

### MK2 — Ads revenue conflicts with sales revenue

Inputs should model a realistic mismatch where raw numbers cannot be compared blindly.

Example:
- Ads reported revenue is gross
- sales source reports net
- currency/basis/scope must be compatible before comparison

Required behavior:
- either reconcile through declared relationships if sufficient evidence exists
- or return conflict/insufficient result if unreconciled
- never treat equal-looking or mismatched-basis numbers as automatically equivalent

### MK3 — budget change action

Intent:
Change one exact campaign budget.

Required behavior:
- relevant evidence must be sufficient
- approval binds exact campaign/action/value
- accepted != verified
- readback must confirm exact campaign and requested budget
- wrong scope/value/readback => failure
- idempotency prevents duplicate side effect

## E-commerce proof

Implement at least THREE deterministic synthetic scenarios/tests.

### EC1 — duplicate reorder

Intent:
Restock one exact SKU.

Required behavior:
- same idempotency key + same payload => same receipt/no duplicate
- same key + changed quantity/SKU => idempotency conflict

### EC2 — inventory/order evidence conflict or insufficiency

Example:
- inventory snapshot says low stock
- pending orders or supplier state changes effective availability
- one required source missing or stale/insufficient

Required behavior:
- do not declare stock safe/replenished without sufficient evidence
- preserve uncertainty or conflict explicitly

### EC3 — accepted restock not yet fulfilled / failed readback

Flow:
- restock action accepted
- later inventory/supplier readback fails or does not show requested state

Required behavior:
- accepted != fulfilled
- final verification failure
- exact SKU/resource/quantity correlation

## Cross-domain proof

Add regression proving one shared engine can execute all of:

- DevOps
- Mechanical
- Inventory
- Marketing
- E-commerce

without inspecting domain names.

If the contract is extended, all Agent B scenarios must continue to pass unchanged where possible.
Prefer backward-compatible additions with sensible defaults.

## Tests

Run:

```bash
python -m unittest discover -s muse_eval/tests -v
git diff --check
```

Acceptance requires:

- all previous 156 tests still pass
- all new tests pass
- no skipped tests hiding incomplete work
- frozen/P1 integrity guard still passes
- no domain-specific dispatch in generic engine
- no production claims

## Documentation

Update `muse_eval/domains/README.md` to clearly separate:

Implemented synthetic proofs:
- Marketing
- E-commerce
- DevOps
- Mechanical Engineering
- Inventory generic extension proof

Not implemented:
- real Meta Ads API
- real commerce platform
- Kubernetes/cloud
- PLC/SCADA/sensors
- production IAM
- durable/concurrent ledger
- real physical safety guarantees

Document exactly which concepts are generic and which domain-specific rules are declarative data.

## Final report

Report:

1. exact changed files
2. exact final test count
3. whether Agent B tests remained unchanged/passing
4. whether any existing P1 model-core file changed
5. whether frozen files changed
6. exact commit SHA after normal push
7. any limitation that prevented fully generic expression

Do not merge to main. Push only to `codex/muse-domains-marketing-ecommerce`.
