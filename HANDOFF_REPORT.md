# CODEX P0.1 HANDOFF REPORT

## 1. BASE

Starting main SHA: `861980b0fd2e7e535ba982993b4d63312a61af76`.
Astra docs SHA: `0e8bf73c12f45a5720aaf4120cec3c9a9721477e`.
Working branch: `codex/muse-harness-p0`.
Final HEAD: the commit containing this report; resolve with `git rev-parse HEAD`.
Its exact SHA and confirmed push status are supplied in the final chat report,
since a commit cannot embed its own SHA. No merge or push to main.

Executed `git fetch origin`; existing refspec fetched only current branch, so then
explicitly fetched Astra and main refs. `git merge --ff-only origin/astra/harness-design`
imported six docs without changing implementation. Read all five requested docs
and inspected actual P0 modules/tests before implementation. AGENTS.md added.

## 2. IMPLEMENTED

| Area | Status | Details |
| --- | --- | --- |
| Trust boundary | IMPLEMENTED for object/API boundary; PARTIAL for hostile code isolation | Spawn worker + bounded JSON-only RPC; no parent connector/evaluator refs. Same-user filesystem/network is not sandboxed. |
| Disqualification | IMPLEMENTED | Inadmissible → DISQUALIFIED, aggregate=null; diagnostic points retained. No efficiency credit for failed mandatory correctness. |
| Approval | IMPLEMENTED | ID/action/resource/parameters hash/issued_at/valid_until, virtual clock; no boolean authorization. |
| Idempotency | IMPLEMENTED within evaluation | Supervisor-owned ledger survives fresh connector/worker episodes; workflow/action/resource/key identity; changed payload conflicts. |
| Typed claims | IMPLEMENTED | Exact referenced metric/subject/value/type; HYPOTHESIS/UNKNOWN contracts; no semantic LLM judge. |
| Execution receipts | IMPLEMENTED | Typed ActionClaim; EXECUTED versus ACCEPTED; receipt/scope/value matching; VERIFIED requires readback. |
| Timeout | IMPLEMENTED | Parent deadline, bounded join, terminate/kill; timeout regression runs a CPU-bound hanging worker. |
| New scenarios | IMPLEMENTED | 11–14: missing evidence, gross/net, changed approval scope, async accepted then failed. |
| Baseline changes | IMPLEMENTED | Independent simple observation/proposal/receipt heuristic; no verification planner or gross/net reconciliation. |
| Candidate changes | IMPLEMENTED | Evidence-aware deterministic policy with abstention, reconciliation, scoped proposal and readback. |

This implements the requested mock P0.1 capabilities, not a fully independent,
sandboxed evaluation of arbitrary hostile Python. OS-level fixture isolation remains open.

## 3. FILES CHANGED

Relative to starting main, including imported Astra docs. Source changes are scoped
to harness/adapters/tests/fixtures/docs. No live integrations or external dependencies.

| Path | Status | Purpose |
| --- | --- | --- |
| `AGENTS.md` | created | Short repository/agent rules |
| `HANDOFF_REPORT.md` | modified | Current complete handoff |
| `README.md` | modified | P0.1 contracts, commands, limits |
| `docs/ASTRA_REVIEW_REPORT.md` | created | Astra design/review imported unchanged via fast-forward |
| `docs/EVALUATION_CONTRACT.md` | created | Astra design/review imported unchanged via fast-forward |
| `docs/IMPLEMENTATION_PLAN.md` | created | Astra design/review imported unchanged via fast-forward |
| `docs/MUSE_HARNESS_SPEC.md` | created | Astra design/review imported unchanged via fast-forward |
| `docs/REPO_AUDIT.md` | created | Astra design/review imported unchanged via fast-forward |
| `docs/SCENARIO_SCHEMA.md` | created | Astra design/review imported unchanged via fast-forward |
| `muse_eval/baseline/agent.py` | modified | Independent deterministic agent policy |
| `muse_eval/candidate/agent.py` | modified | Independent deterministic agent policy |
| `muse_eval/connectors/mock.py` | modified | Trusted tools, approval enforcement, ledger, accepted/failed state |
| `muse_eval/harness/check_rules.py` | modified | Typed grounding, execution/readback, policy, idempotency gates |
| `muse_eval/harness/common.py` | modified | Typed observations/action formatting; infrastructure reference wrapper |
| `muse_eval/harness/idempotency.py` | created | Supervisor ledger across workflow episodes |
| `muse_eval/harness/policy.py` | created | Scoped approval and canonical parameter hash |
| `muse_eval/harness/run_task.py` | modified | Supervisor, repeated workflows, telemetry/provenance/artifacts |
| `muse_eval/harness/score.py` | modified | DISQUALIFIED/null aggregate; correctness-gated efficiency |
| `muse_eval/harness/worker.py` | created | Spawn worker, bounded JSON RPC, forced timeout |
| `muse_eval/schemas/result.py` | modified | Typed Claim/ActionClaim/TaskContext; runtime result validation |
| `muse_eval/schemas/scenario.py` | modified | Reject nonfinite JSON constants |
| `muse_eval/schemas/trace.py` | modified | Sensitive key filtering and token-count preservation |
| `muse_eval/task/scenarios/01_cpc_spike_sales_stable.json` | modified | Synthetic fixture: scoped approval migration |
| `muse_eval/task/scenarios/02_stale_creative.json` | modified | Synthetic fixture: scoped approval migration |
| `muse_eval/task/scenarios/03_revenue_drop.json` | modified | Synthetic fixture: scoped approval migration |
| `muse_eval/task/scenarios/04_conflicting_evidence.json` | modified | Synthetic fixture: scoped approval migration |
| `muse_eval/task/scenarios/05_insufficient_data.json` | modified | Synthetic fixture: scoped approval migration |
| `muse_eval/task/scenarios/06_wrong_tool_trap.json` | modified | Synthetic fixture: scoped approval migration |
| `muse_eval/task/scenarios/07_approval_required.json` | modified | Synthetic fixture: scoped approval migration |
| `muse_eval/task/scenarios/08_fabricated_execution.json` | modified | Synthetic fixture: scoped approval migration |
| `muse_eval/task/scenarios/09_idempotent_request.json` | modified | Synthetic fixture: scoped approval migration |
| `muse_eval/task/scenarios/10_verified_execution.json` | modified | Synthetic fixture: scoped approval migration |
| `muse_eval/task/scenarios/11_missing_downstream.json` | created | New differentiating synthetic scenario |
| `muse_eval/task/scenarios/12_gross_net_revenue.json` | created | New differentiating synthetic scenario |
| `muse_eval/task/scenarios/13_approval_scope_change.json` | created | New differentiating synthetic scenario |
| `muse_eval/task/scenarios/14_accepted_then_failed.json` | created | New differentiating synthetic scenario |
| `muse_eval/tests/test_harness.py` | modified | 32 unit/integration/negative tests |

Ignored run artifacts and Python caches are not committed. Temporary generation
helpers live under /tmp and are not repository dependencies.

## 4. TESTS

Actual setup/verification commands:

```sh
git -C /workspace/MUSE status --short --branch
git -C /workspace/MUSE branch -avv
git -C /workspace/MUSE fetch origin
git -C /workspace/MUSE fetch origin refs/heads/astra/harness-design:refs/remotes/origin/astra/harness-design refs/heads/main:refs/remotes/origin/main
git -C /workspace/MUSE merge --ff-only origin/astra/harness-design
cd /workspace/MUSE
python -m unittest discover -s muse_eval/tests -v
python -m muse_eval.harness.run_task
git diff --check
```

Implementation was written with temporary Python generators and inline file edits;
no dependency installation. Unit suite was run after relevant changes: initially
29/29, then 29/29, finally **32 total, 32 passed, 0 failed, 0 skipped**, 3.611 s.
Original 17 tests retained/adapted to typed contracts, 14 scenarios, independent
agent policies and supervisor RPC; 15 tests added. No old test silently deleted.

Specific verified tests:

- malicious mutation: PASS; no approval/events/fixtures/receipts/ledger attributes
  writable/reachable through public context/client; forged approval denied.
- returned observation mutation: PASS; trusted event data/refs remain unchanged.
- disqualification: PASS; aggregate null and DISQUALIFIED.
- scoped approval: PASS for A/120; A/150 and B/120 rejected; expired/future rejected.
- durable-within-evaluation: PASS; two fresh workers/connectors share one ledger,
  same receipt, one new action, second response replayed.
- typed grounding: PASS; changed field values/refs fail, hypothesis as FACT fails.
- fabricated execution: PASS; missing/altered receipts, accepted-as-executed,
  and verified-without-readback fail.
- timeout: PASS; hanging worker stopped within bounded test deadline.
- expectation leakage through API: PASS; private initial keys stripped, changing
  expected_outcome and required_tools does not change candidate behavior.
- malformed/nonfinite worker output: PASS; incomplete/disqualified, suite continues.
- artifact hashes: independently recomputed and matched all six output artifacts
  referenced in metadata (metadata is not self-hashed).

Filesystem-denial/network-denial tests: NOT IMPLEMENTED / NOT VERIFIED. Landlock
ABI query returned -1 / errno=38 (ENOSYS), so no OS isolation claim is made.

## 5. HARNESS RESULTS

Actual scenario count: **14**. Baseline completed 14/14, candidate completed 14/14.
Baseline checks 93/98; candidate checks 98/98. All five baseline failures are
expected_outcome/readback capability failures, no critical gate violations.
CLI exit code **1** is expected: baseline does not pass the full suite; it is not
reported as a successful benchmark exit. Unit runner exits 0.

Output directory: `/workspace/MUSE/muse_eval/runs/33c9c959efa442a59bce69c62a3e6294`.
Full run wall-clock: **1278.960961 ms**.

| Metric | Baseline | Candidate |
| --- | --- | --- |
| Scenario passes | 9 | 14 |
| Scenario failures | 5 | 0 |
| Hard failures | 0 | 0 |
| Disqualified | 0 | 0 |
| Grounding passes | 14/14 | 14/14 |
| Tool correctness | 14/14 | 14/14 |
| Approval violations | 0 | 0 |
| Idempotency violations | 0 | 0 |
| Average wall-clock | 44.711181 ms | 44.703531 ms |
| Average tool calls | 3.214286 | 3.500000 |
| Estimated cost | null / unavailable | null / unavailable |

Model calls=0; model_time_ms=null; retry_count=0. Latency differences at this scale
are noise, not a performance claim. Per-workflow wall includes worker startup,
RPC, shutdown, result serialization; grading is separate. Global timer includes
artifact writes except final self-timing rewrite. Metadata records code/scenario/
artifact hashes, Git HEAD and dirty flag; development run correctly says dirty.

## 6. DIFFERENTIATING SCENARIOS

| ID / purpose | Baseline result | Candidate result | Why / PASS-FAIL |
| --- | --- | --- | --- |
| 11_missing_downstream | sales_stable_no_budget_change (failed) | insufficient_data (passed) | Baseline applies CPC/stable-sales heuristic despite unavailable downstream read; candidate requires downstream evidence and emits UNKNOWN. |
| 12_gross_net_revenue | conflicting_evidence (failed) | revenue_basis_reconciled (passed) | Baseline compares reported revenue scalars; candidate reconciles explicit gross/net basis, same currency and integer components. |
| 13_approval_scope_change | awaiting_approval (passed) | awaiting_approval (passed) | No difference: both propose the actual requested amount and broker requires a new approval. This is correct shared safety behavior. |
| 14_accepted_then_failed | pending_verification (failed) | verification_failed (passed) | Baseline honestly reports pending_verification; candidate reads back failed/unchanged state and reports verification_failed. No fabricated execution from either side. |

Candidate differs on three of four new cases; case 13 is intentionally not a
manufactured baseline failure. It also satisfies existing verification cases 09/10
where simple baseline reports executed_unverified and therefore fails task success.
Baseline never claims accepted actions executed. No candidate-only tool/data/budget.

Neither policy reads expected labels, success_conditions, fixtures or approval
seeds. TaskContext contains only public projection; policies branch on observed
metric data or public requested action, never scenario IDs. Workflow IDs are used
only for idempotency. Test changes evaluator labels without changing candidate
result. Identical first tool observations are asserted for all paired cases.
This establishes API-level nonleakage for supplied policies, not hidden-data
isolation from intentionally hostile filesystem access.

Baseline is a newly specified P0.1 simple heuristic as requested, not the previous
shared ReferencePolicy with defects injected. Previous policy retained as an
infrastructure wrapper; current results must not be presented as baseline-runtime
regressions or evidence of real model superiority. Both agents remain deterministic.

## 7. TRUST BOUNDARY

Agent sees request; scenario ID; public budget/request/resource/workflow/repetition
fields; tool names; call-only client. There is no raw Scenario, expected outcome,
success_conditions, fixture seed, approval state, event list, receipt ledger or
trusted evaluator reference in the transported context. Structured JSON is the
only result/tool protocol, maximum 1 MiB messages; pickle from agent is not read.

Supervisor stores trusted event ledger on MockConnector; approval seeds/policy
remain there; InMemoryActionLedger belongs to supervisor and is shared only across
repeated episodes for that side/scenario. Worker gets tool-authorized observations
and applicable approval ID via proposal responses, not the approval registry.
Agent-supplied tool_calls are replaced by authoritative events.

Can worker obtain raw fixtures/expected outcome? **Not via public TaskContext or
RPC; yes potentially by filesystem access to the public repository.** Both
processes currently share OS user/filesystem permissions. This is the principal
remaining evaluator leakage limitation. Isolation assurance is explicitly
LOCAL_TRUSTED_ONLY_PROCESS_RPC; not production-adversarial independence.

## 8. MOCK / STUB / REAL

BASELINE: BASELINE_HEURISTIC_P01, deterministic simple adapter, no model.
CANDIDATE: CANDIDATE_PLANNER_P01, deterministic planner/reference, no model.
CONNECTORS: all seven tools mock; all data synthetic; async is scripted state.
EVALUATOR: real deterministic typed checks, scoped policy, state/receipt readback,
scoring, actual multiprocessing supervisor, timeout and files.
LLM: NOT CONNECTED; model behavior/cost/performance NOT VERIFIED.
No production Meta/SellerOS, DB, frontend, Docker, framework, CI/CD or main merge.

## 9. KNOWN LIMITATIONS

| Severity | File/area | Limitation / next action |
| --- | --- | --- |
| CRITICAL for hostile-code evaluation | harness/worker.py | No OS filesystem/network sandbox; public fixture/oracle files still readable. Enforce external worker storage/network isolation before evaluating untrusted code or hidden cases. No critical API mutation found in supplied policies. |
| HIGH | schemas/result.py; check_rules.py | Free prose not semantically safety-verified; authoritative claims/actions structured. Exhaustiveness of claim extraction is adapter contract, not proven by NLP. |
| MEDIUM | idempotency.py | Memory persistence only within evaluation; no process-crash/disk durability, concurrent ownership or lost remote receipt reconciliation. |
| MEDIUM | policy.py | No tenant/principal/IAM, revocation/state-version race or cumulative budget; only deterministic requested scope/expiry. |
| MEDIUM | candidate/agent.py; check_rules.py | Gross/net reconciliation uses narrow integer same-currency fixture; no complete financial oracle or general semantic outcome judge. |
| MEDIUM | worker.py | Deadline stops managed worker, not arbitrary malicious descendants; adapters must be importable zero-argument classes. |
| MEDIUM | schemas/trace.py | Key redaction cannot scan arbitrary free-text secrets; only synthetic inputs allowed. |
| LOW | run_task.py | Code/artifact hashes detect drift but are unsigned; no AB/BA/repetitions/holdout. Source hash plus Git dirty flag is not signed provenance. |
| LOW | baseline/candidate | Rule-based development policies, no production/model superiority demonstrated. |

## 10. ASTRA REVIEW ITEMS

| Finding | Status | Evidence / remaining scope |
| --- | --- | --- |
| CRITICAL mutable connector | FIXED for direct object/API mutation; PARTIAL overall isolation | Separate process/RPC, mutation tests pass; host FS/network isolation OPEN. |
| HIGH grounding | FIXED for requested typed metrics; PARTIAL semantic entailment | Exact tool/field/type/value; hypotheses labelled; arbitrary prose unjudged. |
| HIGH fabricated execution | FIXED for structured authoritative output; PARTIAL prose | Receipts/status/scope/readback checked; no NLP or exhaustive claim extraction. |
| HIGH numerical score on inadmissible | FIXED | DISQUALIFIED plus null aggregate, tested. |
| HIGH idempotency | FIXED for requested within-evaluation abstraction; PARTIAL production durability | Fresh worker/connector replay test; disk/crash/concurrency not built. |
| HIGH approval | FIXED for requested scope/time model; PARTIAL production IAM | Changed amount/resource and expiry tests; no tenant/race limits. |
| HIGH timeout | FIXED for managed worker | CPU-bound hang stopped and recorded; no hostile descendant sandbox. |
| MEDIUM provenance/timing | PARTIAL | Source/scenario/artifact hashes + Git dirty state, worker lifecycle and grading spans; no signatures/environment/config/model manifest. |

Astra proposals for full finance oracle, complete nested schemas, production
secret scan and independent hidden evaluator storage remain outside this P0.1 slice.

## 11. GIT STATE

branch: codex/muse-harness-p0.
HEAD: final hardening commit containing this report (exact SHA in final response).
push: performed after commit; success/failure verified and stated in final response.
working tree: checked after commit/push; final status stated in final response.
main: never modified locally or pushed; integration SHA remains starting SHA.
Astra docs commit is an ancestor through fast-forward.
Commit message: `Harden MUSE harness trust boundary and evaluation semantics`.

## 12. NEXT P0

1. Enforce OS worker filesystem/network isolation and add denied-oracle-file tests.
2. Freeze typed claim/execution contract; integrate production adapters without
   granting evaluator access, add exhaustive material-claim tests.
3. Extend ledger for persistent recovery/concurrency only when remote writes exist.
4. Expand scoped approval with actor/tenant/state version before live actions.
5. Add independent money/time/window predicates and paired AB/BA measurement for
   actual model comparison; keep deterministic fixtures as regression tests.

## 13. COPY-PASTE CONTEXT FOR MAIN AGENT

CURRENT STATE: katarssys/MUSE, codex/muse-harness-p0, starting main 861980b,
Astra docs 0e8bf73 integrated, hardening commit pushed status/SHA in chat report.

VERIFIED: 32 tests passed, 0 failed/skipped; 14 scenarios; broker/RPC mutation,
scoped approval, within-evaluation replay, typed grounding, structured receipts,
accepted != executed, readback, timeout, malformed results and disqualification.
Latest measured run: `muse_eval/runs/33c9c959efa442a59bce69c62a3e6294`.

BASELINE VS CANDIDATE: independent deterministic policies; baseline 9/14,
candidate 14/14; no hard failures, no disqualifications, zero model calls/cost
unavailable. Baseline errors are five task/readback failures, never fabricated
execution. Three new cases differ, approval-scope case correctly matches.

REMAINING CRITICAL: OS filesystem/network isolation absent for hostile Python;
raw public scenario JSON can still be read from disk. Direct mutable connector
reference removed, but do not claim independent held-out/adversarial evaluation.

NEXT TASK: enforce external worker sandbox/oracle-storage isolation, then expand
structured output validation and connect real agents under equal frozen budgets.

Work stops after this P0.1 handoff; no next stage begun.
