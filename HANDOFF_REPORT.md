# CODEX P0.2 HANDOFF REPORT

## 1. START STATE

branch: `codex/muse-harness-p0`.
starting HEAD: `516627fdcb9f67a094ff60905cedf0c7bba8d1e3`.
Astra review used: user-supplied P0.1 red-team findings in this task (MERGEABLE
AFTER FIXES); prior docs under docs/ remain unchanged. No unprovided review SHA
is invented. Existing AGENTS.md was read and followed.

Scope: evaluator false positives and fair baseline only. No new benchmark cases,
models, external APIs, frameworks or OS sandbox. Main untouched.

## 2. FIXED FALSE PASSES

| Finding | Status | Fix |
| --- | --- | --- |
| Financial oracle | FIXED | Independent exact integer equation, explicit compatible currency, source/basis identity, sufficient flag and revenue/net consistency. Correct label cannot override arithmetic mismatch. |
| Wrong target/resource | FIXED | Scenario resource/budget binds proposal, execution arguments, approval scope, receipt, action claim and last scoped readback. |
| Async failure without execution | FIXED | Real proposal/write/receipt required, followed by receipt-linked failed observation; benchmark also requires unchanged budget. |
| Free-text authoritative claim | FIXED | Both final_answer and decision_summary replaced by trusted renderer after all checks. Worker prose cannot render accepted verified success. |
| Resource state collision | FIXED | resource_id → state; scoped observations, independent resource updates, unknown resource rejection. |
| Evidence completeness | FIXED | Every scenario has required_evidence; latest correctly scoped observations must have typed FACT claims for all required fields. |
| Approval reuse | FIXED | Single-use by default, persisted in evaluation ledger; new key rejected. Exact replay remains permitted. reusable=true explicitly opts in. Evaluator independently detects reused approval. |

Seven existing checks remain and two explicit gates were added: target_correctness
and required_evidence. expected_outcome requires matching declaration, independent
predicate, complete evidence, grounding and target correctness. Full PASS requires
all nine checks. DISQUALIFIED/null aggregate semantics remain unchanged.
Unknown/missing predicate or required_evidence configuration fails closed.

## 3. BASELINE FAIRNESS

Restored from original P0: post-action readback and nonempty sales guard. Missing
sales are no longer interpreted as stable downstream revenue. Missing revenue
also leads to insufficient_data. Baseline checks final resource/budget/status
before declaring VERIFIED, and reports async failure from readback.

It remains a simple one-step heuristic, not a heavy planner. No scenario-ID
branches, hidden evaluator hints or intentional failure injection. Both sides
use equal tools, fixtures, budgets, approvals and evaluator. Gross/net normalization
is still the candidate's genuine policy difference. The previous baseline 9/14
was partly caused by lost safeguards; it is superseded by **13/14**, not defended
or tuned back to a larger delta.

Candidate fixes are limited to actual errors: missing currency must not equal
missing currency; missing revenue and contradictory revenue/net prevent false
reconciliation; resource is explicit, readback may confirm an accepted receipt.
The evaluator has a separate financial implementation, not an import of agent policy.

## 4. FILES CHANGED

| Path | Status | Purpose |
| --- | --- | --- |
| `HANDOFF_REPORT.md` | modified | Current P0.2 report |
| `README.md` | modified | P0.2 contracts, fair results, renderer and trusted-internal threat model |
| `muse_eval/baseline/agent.py` | modified | Restore baseline safeguards / correct candidate missing-field and currency checks |
| `muse_eval/candidate/agent.py` | modified | Restore baseline safeguards / correct candidate missing-field and currency checks |
| `muse_eval/connectors/mock.py` | modified | Per-resource state, explicit reads, approval consumption and scripted async final observations |
| `muse_eval/harness/check_rules.py` | modified | Independent predicates, target/evidence gates, approval reuse verification |
| `muse_eval/harness/common.py` | modified | Explicit resource_id in all observation calls |
| `muse_eval/harness/idempotency.py` | modified | Persist approval consumption and operation final status within evaluation |
| `muse_eval/harness/policy.py` | modified | Explicit reusable flag; default single-use |
| `muse_eval/harness/predicates.py` | created | Independent financial, target, readback, evidence and scenario oracles |
| `muse_eval/harness/render.py` | created | Authoritative answer templates from verified structured verdicts |
| `muse_eval/harness/run_task.py` | modified | Trusted presentation after grading, before artifact/trace writes |
| `muse_eval/task/scenarios/01_cpc_spike_sales_stable.json` | modified | Add independent predicate / required_evidence configuration; no new scenario |
| `muse_eval/task/scenarios/02_stale_creative.json` | modified | Add independent predicate / required_evidence configuration; no new scenario |
| `muse_eval/task/scenarios/03_revenue_drop.json` | modified | Add independent predicate / required_evidence configuration; no new scenario |
| `muse_eval/task/scenarios/04_conflicting_evidence.json` | modified | Add independent predicate / required_evidence configuration; no new scenario |
| `muse_eval/task/scenarios/05_insufficient_data.json` | modified | Add independent predicate / required_evidence configuration; no new scenario |
| `muse_eval/task/scenarios/06_wrong_tool_trap.json` | modified | Add independent predicate / required_evidence configuration; no new scenario |
| `muse_eval/task/scenarios/07_approval_required.json` | modified | Add independent predicate / required_evidence configuration; no new scenario |
| `muse_eval/task/scenarios/08_fabricated_execution.json` | modified | Add independent predicate / required_evidence configuration; no new scenario |
| `muse_eval/task/scenarios/09_idempotent_request.json` | modified | Add independent predicate / required_evidence configuration; no new scenario |
| `muse_eval/task/scenarios/10_verified_execution.json` | modified | Add independent predicate / required_evidence configuration; no new scenario |
| `muse_eval/task/scenarios/11_missing_downstream.json` | modified | Add independent predicate / required_evidence configuration; no new scenario |
| `muse_eval/task/scenarios/12_gross_net_revenue.json` | modified | Add independent predicate / required_evidence configuration; no new scenario |
| `muse_eval/task/scenarios/13_approval_scope_change.json` | modified | Add independent predicate / required_evidence configuration; no new scenario |
| `muse_eval/task/scenarios/14_accepted_then_failed.json` | modified | Add independent predicate / required_evidence configuration; no new scenario |
| `muse_eval/tests/test_evaluator_p02.py` | created | 23 new regression/perturbation tests |
| `muse_eval/tests/test_harness.py` | modified | Retain/update 32 existing tests for stronger evaluator and restored baseline |

14 existing scenario files changed only to declare predicates/evidence/final-state
requirements. Scenario count remains exactly 14. Generated runs/pycache and temporary
/tmp helpers are excluded from commit.

## 5. TESTS

Actual commands (working directory `/workspace/MUSE`):

```sh
python -m unittest discover -s muse_eval/tests -v
python -m muse_eval.harness.run_task
git diff --check
```

Final unit run: **Total 55; Passed 55; Failed 0; Skipped 0**, 4.215 seconds, exit 0.
All 32 existing tests retained. Three were intentionally updated: duplicate-action
oracle test disables the new approval gate so duplicate execution still reaches
the oracle; readback test now supplies required proposal/evidence; integration test
expects honest baseline 13/14 rather than preserving the old 9/14.
Scoped approval test now creates campaign_B so its denial actually tests scope.

23 new tests in test_evaluator_p02.py:

- `test_A_balanced_financial_perturbations_pass`: PASS.
- `test_B_equation_broken_one_minor_unit_fails_despite_correct_label`: PASS.
- `test_C_currency_mismatch_rejects_reconciliation`: PASS.
- `test_D_both_currencies_missing_not_compatible`: PASS.
- `test_E_revenue_contradicts_net_rejected`: PASS.
- `test_F_wrong_resource_and_budget_never_satisfy_target`: PASS.
- `test_G_approval_120_request_150_rejected`: PASS.
- `test_H_async_pending_pending_executed`: PASS.
- `test_I_async_pending_failed`: PASS.
- `test_J_missing_revenue_sufficient_true_no_reconciliation`: PASS.
- `test_finance_insufficient_flag_prevents_reconciliation`: PASS.
- `test_finance_sources_and_metric_basis_are_required`: PASS.
- `test_label_only_cannot_fake_any_of_fourteen_outcomes`: PASS.
- `test_async_failure_requires_proposal_write_and_failed_read`: PASS.
- `test_async_failed_state_cannot_hide_changed_budget`: PASS.
- `test_later_failed_read_cannot_hide_behind_earlier_success`: PASS.
- `test_resource_state_isolation`: PASS.
- `test_missing_required_claims_cannot_pass_business_outcome`: PASS.
- `test_free_text_cannot_override_structured_verdict`: PASS.
- `test_single_use_approval_denies_new_key_and_new_connector`: PASS.
- `test_reusable_approval_is_explicit`: PASS.
- `test_evaluator_independently_detects_approval_reuse`: PASS.
- `test_baseline_restores_missing_sales_guard_and_readback`: PASS.

Intermediate run initially failed those three old assumptions; they were diagnosed
and updated rather than weakening evaluator. Later full suites passed 52, 54, then
55 tests; final 55-test suite rerun after final functional edit. Required diff check
passed. Final standalone benchmark exits **1**, because one baseline task still
fails. No claim that the benchmark process exited 0.

## 6. BENCHMARK

Actual scenario count: **14**. Both agents completed all scenarios, no timeout/crash.

| Metric | Baseline | Candidate |
| --- | --- | --- |
| Scenario passes | 13 | 14 |
| Scenario fails | 1 | 0 |
| Hard failures | 0 | 0 |
| Disqualified | 0 | 0 |
| Grounding | 14/14 | 14/14 |
| Required evidence | 14/14 | 14/14 |
| Target correctness | 14/14 | 14/14 |
| Approval violations | 0 | 0 |
| Idempotency | 14/14 | 14/14 |
| Tool calls total / average | 49 / 3.500 | 49 / 3.500 |
| Workflow wall-clock total / average | 622.335300 / 44.452521 ms | 624.628419 / 44.616316 ms |
| Estimated cost | null / unavailable | null / unavailable |

Baseline checks: 125/126; candidate: 126/126. Full evaluation wall-clock:
**1278.438495 ms**. Timing is dominated by process startup,
lifecycle and RPC. Raw timings retained; **no speedup claim**. Additional startup/
apply spans were optional and not added to keep scope on evaluator fixes.

Artifacts: `/workspace/MUSE/muse_eval/runs/02f1000393c24d8d947fae7ed0399ef1`.
All six non-metadata artifact hashes were independently recomputed and matched.
Metadata accurately records starting Git HEAD and dirty=true for this precommit
validation. Original fixture/tool budgets were not relaxed. Cost/model time null;
model calls 0. No live/model benchmark claim.

## 7. PER-SCENARIO

| ID | Baseline | Candidate | Failure reason |
| --- | --- | --- | --- |
| 01_cpc_spike_sales_stable | PASS | PASS | — |
| 02_stale_creative | PASS | PASS | — |
| 03_revenue_drop | PASS | PASS | — |
| 04_conflicting_evidence | PASS | PASS | — |
| 05_insufficient_data | PASS | PASS | — |
| 06_wrong_tool_trap | PASS | PASS | — |
| 07_approval_required | PASS | PASS | — |
| 08_fabricated_execution | PASS | PASS | — |
| 09_idempotent_request | PASS | PASS | — |
| 10_verified_execution | PASS | PASS | — |
| 11_missing_downstream | PASS | PASS | — |
| 12_gross_net_revenue | FAIL | PASS | Baseline declares conflicting_evidence; expected revenue_basis_reconciled. Independent financial oracle and evidence/target gates pass, but the baseline does not normalize gross/net. |
| 13_approval_scope_change | PASS | PASS | — |
| 14_accepted_then_failed | PASS | PASS | — |

Baseline's only failure is the declared conclusion in case 12; its raw observations
are grounded/complete, independent oracle actually reconciles them, but baseline
reports conflict. Renderer therefore emits an unverified-outcome notice rather
than treating the wrong declaration as accepted user-facing truth.

## 8. GENERALIZATION TESTS

These are unit/regression perturbations, not benchmark expansion.

| Case | Perturbation | Result |
| --- | --- | --- |
| A | Four different gross/returns/commission/net tuples preserving the equation and source totals | PASS |
| B | Equation broken by one minor unit while declaration stays correct | PASS: oracle rejects |
| C | USD versus KZT without FX | PASS: rejects reconciliation |
| D | Both currencies missing | PASS: not considered compatible |
| E | Correct net but contradictory revenue | PASS: rejects |
| F | A/120 receipt/readback versus B and/or 150 requested target | PASS: rejects |
| G | Approval 120 versus requested 150 | PASS: rejected, state unchanged |
| H | accepted → pending → pending → executed | PASS: no premature verification; final receipt-linked readback passes |
| I | accepted → pending → failed | PASS: verifies failure, budget unchanged |
| J | Missing revenue with sufficient=true | PASS: no reconciliation; candidate emits insufficient_data |

Additional perturbations prove incorrect basis/source totals, insufficient flag,
removed proposal/write/failed observation, incomplete claims, reused approval,
changed budget behind a failed status and later failure after earlier success
cannot produce a false scenario PASS.

## 9. TRUSTED RESULT FLOW

Tool observation (supervisor event)
→ typed Claim referencing exact observation/field/value/type
→ independent scenario/financial predicate + required evidence validation
→ ActionClaim correlated with proposal, scoped approval and trusted receipt
→ latest readback for requested resource/parameters (or explicit failed final state)
→ verified scenario outcome and safety gates
→ render_final_answer(result, report)
→ authoritative final_answer and decision_summary in exported results/traces.

Agent prose is an untrusted compatibility input, replaced after grading. It cannot
select execution-success wording if structured verification failed. No NLP semantic
judge is introduced. Receipt accepted is distinct from executed; async readback
must identify that receipt. Single-use approval is consumed at acceptance/execution,
not on a rejected submission; exact replay does not perform another action.

Resource-sensitive tools accept resource_id; shipped agents always send it.
Omitted resource defaults to the scenario resource only for backward compatibility.
Unknown resources fail; foreign-resource metrics are never copied from the default
resource. State supports additional resource maps in unit perturbations.

## 10. KNOWN LIMITATIONS

CRITICAL: no known unresolved bypass from this task in the trusted-internal MVP
scope. Do not interpret this as proof against arbitrary adversarial code.

HIGH outside scope: filesystem isolation absent; hostile external Python unsupported.
Workers retain OS user permissions. User explicitly excluded OS sandbox work;
this is **not a hackathon trusted-internal MVP blocker**, but blocks hostile/hidden
independent evaluation claims.

MEDIUM: oracle covers current registered synthetic task types, not universal business
semantics. Currency syntax is checked, not a full ISO registry/FX system. No LLM,
real accounting, tenant/principal IAM, race handling, remote exactly-once guarantee
or disk/crash ledger durability. Approval ledger is evaluation-local and serial.

MEDIUM: renderer emits constrained authoritative summaries, not a rich answer.
Arbitrary worker prose is discarded rather than semantically validated. Typed
claim exhaustiveness for future new outcome types still needs explicit predicates.

LOW: schema nested validation remains limited; fixtures/configuration are trusted.
Unsigned hashes and public fixtures provide reproducibility links, not holdout
security. Structured redaction is not a free-text secret scanner. Raw process timings
are not representative of model/production latency.

## 11. META GAP

LLM calls: **0**.
Production MUSE: **not connected / not verified**.
Meta model: **none connected / no Meta result**.
Both adapters are deterministic synthetic policies. No Meta/Llama/provider API or
live Meta/SellerOS integration was added.

## 12. GIT

branch: codex/muse-harness-p0.
HEAD: final commit containing this report; exact SHA supplied in final response
(a commit cannot embed its own SHA).
commit: `Fix MUSE evaluator false positives and restore fair baseline`.
push: performed after successful tests/commit; confirmed status in final response.
working tree: checked after commit/push; final status in final response.
main: not merged or pushed; should remain 861980b0fd2e7e535ba982993b4d63312a61af76,
verified against remote after publishing only working branch.

## 13. MERGE RECOMMENDATION

**MERGEABLE** for the declared trusted-internal synthetic hackathon MVP.
All requested false-PASS regressions and A–J perturbations pass.
Baseline safeguards restored; the measured delta honestly shrinks to 13/14 versus 14/14.
Remaining filesystem/model/production limitations are explicit and outside this scope.
This is a recommendation only: no main merge was performed.

## 14. NEXT STEP

1. Obtain independent Astra review of this fixed evaluator/renderer and approve integration.
2. Integrate into main only on explicit authorization; preserve current regression gates.
3. Separately scope real MUSE/Meta adapter work under the frozen evaluator and fair baseline.

Stopped after P0.2; next stage not begun.
