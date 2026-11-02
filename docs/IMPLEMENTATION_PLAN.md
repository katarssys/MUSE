# MUSE implementation sequence v1
Research deliverables only; no harness rewrite authorized by this document.

| Phase | Scope | Exit criterion |
|---|---|---|
| 1 | schema, contract, supervisor skeleton + read-only expected boundary | invalid schema rejected; candidate cannot access oracle; manifests pinned |
| 2 | 10 deterministic smoke cases (SCENARIO_SCHEMA) and mock state | expected outcomes independently derivable, scripted faults reproducible |
| 3 | honest baseline runner | all cases runnable incl expected handoff/failure; documented baseline behavior |
| 4 | candidate apply adapter | same public context/tool budget; no evaluator edits |
| 5 | trusted trace and usage | every call/receipt attributable; no secrets, full wall recorded |
| 6 | ten independent checks | forged execution, bad money, approval bypass, duplicate action fail |
| 7 | score and paired report | failed gates never rewarded, missing metrics explicit, formula tested |
| 8 | 50 authored scenarios + 30/10/10 split | independent review; no template leakage; no claimed live validation |
| 9 | SellerOS schema fidelity | verified actual API or explicit synthetic adapter; no invented CRM data |
| 10 | Ads/SignalBridge adapter fidelity | currency/timezone/windows/provenance contract; English synthetic demo |
| 11 | expanded approval/idempotency suite | approval race, crash and concurrent duplication tests pass |
| 12 | conditional medical suite | allowed help and forbidden decisions tested; product flag recorded |
| 13 | protected CI gate | evaluator checkout protected; no required skips; all critical violations block release |
| 14 | incident/replay pipeline | sanitized incident reproduces old failure and gates fix |
| 15 | opt-in live integration tests | owned test tenants, actual API capabilities verified, separate timing/cost reports |

Approval broker and basic idempotency must exist for initial smoke action cases; Phase 11 expands their coverage. Phase order is feature expansion, not permission to bypass safety until later.

## First files after design review
1. schemas/scenario.schema.json and schemas/agent_result.schema.json; JSON Schema contract tests for visibility and invalid values.
2. harness/schema.py, common.py: strict loading, canonical hashes, unique run IDs, versioned manifests.
3. harness/state.py + connectors/mock.py: fresh transactional SQLite state, simple typed read tools.
4. harness/broker.py + policy.py + idempotency.py: scoped RPC, stable operation keys, external approval enforcement before first write.
5. harness/run_task.py + worker.py: same supervisor, timeout/isolation, paired cloned states.
6. baseline/__init__.py then solution/__init__.py; telemetry.py and independent evaluate/check_rules/score as phased above.

Minimal vertical slice: one read-only Ads investigation and one proposed budget action requiring approval, plus repeated action with durable key; inspect receipts/state before expanding. Initial 10 smoke set then generalizes this slice.

## Dependencies and resource discipline
Core stdlib + jsonschema; pytest development only; YAML/HTTP recorder/provider SDK optional and justified separately. No framework installation in research. Record real model costs from first pilot; deterministic connector CI may still spend model tokens, so infrastructure tests use mock model and agent-quality tests use bounded real-model jobs. Provider rate/pricing UNKNOWN until selected, don't invent budget figures.

## Unresolved inputs that do not block deterministic design
Official META rules text; current MUSE/SellerOS/SignalBridge source URLs and interface contracts; chosen Meta model/version/provider; medical inclusion; owner policy thresholds; live tenant/connector permissions. Until resolved, use explicit synthetic fixtures and mark compliance/API claims unverified. No invented official rules or production capabilities.

## Acceptance for moving to code
Versioned schema and integration contract reviewed; first 10 cases have fixtures and independent predicates; baseline budget/model track fixed; trust boundary enforceable; score calibration reserved to pilot. No need to implement live connectors or install a general evaluation framework to begin.
