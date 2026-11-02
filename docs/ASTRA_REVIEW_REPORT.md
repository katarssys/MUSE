# ASTRA REVIEW REPORT

Review date: 2026-11-02. Reviewed main: `861980b0fd2e7e535ba982993b4d63312a61af76`. Scope: architecture/review and documentation only. Implementation files unchanged. All design documents describe proposed target architecture, not implemented capabilities; this report supersedes their earlier statement that no MUSE repository exists. Shared repository is https://github.com/katarssys/MUSE . No separate repository should be created.

## Current Codex P0
Reproduced locally from the pinned GitHub source: `python -m unittest discover -s muse_eval/tests -v`: **17/17 PASS**. Called `run()` on all ten scenarios: baseline **70/70**, candidate **70/70**. This is seven checks × ten cases per adapter, not ten independent check categories. Results show infrastructure/reference-policy consistency, not model capability or candidate advantage.

Implemented: typed dataclass scenario loader; common Agent.apply(TaskContext) contract; fresh mock connector per scenario/side; tool allowlist; fixture-based approval; in-memory idempotent receipt ledger; post-action budget read; seven checks; weighted scoring; tool-event traces; UUID run directories, scenario hashes and timing; negative unit tests. One mock connector class implements seven named tools (five reads, propose, execute). All data synthetic. No model invocation, real routing/planner, replay/live adapter, standalone evaluator process, financial correctness check, schema output validation or CI regression gate.

BaselineAgent and CandidateAgent both inherit ReferencePolicy and differ only by version string. Policy consumes structured initial_state and hardcoded fixture fields, not natural-language request semantics. README accurately discloses these boundaries. `get_leads` is a synthetic tool, not evidence that SellerOS has lead CRM.

## Design alignment
- Same runner/context contract, identical scenario inputs and fresh deepcopy fixture state for each side.
- Honest equality: no artificial baseline degradation.
- Tool authorization checked in connector; caller `approved=True` argument does not authorize writes.
- Receipts verified against successful calls; structured fabricated execution negative tests exist.
- Actual changed mock budget is read after execution in scenarios requiring verification.
- Unknown cost remains null; model calls/retries are zero, not invented usage.
- Sanitized structured traces avoid private reasoning fields.
- Separate run IDs and scenario content hashes exist.

Soup-style protocol partially implemented: sequential same runner yes; isolated OS execution, AB/BA repetitions, independent evaluator, clean per-workflow lifecycle and correctness-before-score admission not yet complete. No Soup code copied according to implementation README; this review adds architecture research only. Soup file/pattern map and licenses are in REPO_AUDIT.md.

## Gaps
Severity is relative to claiming independent MUSE evaluation; current trusted synthetic reference-policy smoke remains useful.

| Severity | Finding / relevant file | Evidence and recommended fix |
|---|---|---|
| CRITICAL | Candidate can change trusted connector state, approval and events; connectors/mock.py, schemas/result.py | TaskContext exposes object with mutable approved/fixtures/events/receipts. Local probe sets approved=True and executes an unapproved budget. Use capability-only client and separate trusted broker/evaluator process; retain explicit trusted-only label until boundary enforced. |
| HIGH | Grounding proves observation copy, not claim entailment; harness/check_rules.py | False claim text with real get_sales payload passes. Add typed financial/numeric/time claims checked against evidence fields; semantic cases require explicit rubric/review, including final_answer. |
| HIGH | Free-text execution claims bypass fabrication checker; harness/check_rules.py | final_answer='I executed a budget change successfully' with no action is not flagged if structured outcome is another code. Validate all material action assertions; start with constrained typed output rendered by trusted code. |
| HIGH | Hard failure still has aggregate points; harness/score.py | score(admissible=False) returns numeric aggregate. CLI/status fails, so current release status is not silently PASS, but consumers can rank invalid scores. Set aggregate=null and explicit DISQUALIFIED before cost/latency reward. No efficiency credit on failed mandatory correctness. |
| HIGH | Idempotency only within one connector instance; connectors/mock.py, harness/common.py | Second run resets receipts; scenario_id key identifies scenario, not durable business operation. Add stable operation ID across restart, durable ledger and reconciliation test after remote commit/lost response. |
| HIGH | Approval boolean has no actor/resource/amount/expiry binding; mock.py | Approval true authorizes any positive budget. Add approval scope/args digest/policy version and atomic owner limits; test changed amount and stale state. |
| HIGH | No real independent outcome/financial oracle; check_rules.py | expected_outcome is string equality; only some scenarios require readback. No Decimal/currency/returns oracle; no typed FACT/HYPOTHESIS. Implement scoped predicates and money schema before finance claims. |
| HIGH | No timeout or crash isolation; run_task.py | Agent.apply runs directly; hanging agent blocks complete evaluation; exceptions in malformed result/checker may abort suite. Restricted worker with timeout and typed output errors. |
| MEDIUM | Scenario/output schemas shallow; schemas/scenario.py, result.py | Only top-level types, no nested fixture/budget/version/currency validation; result dataclass annotations not runtime checks. Add strict nested validation and explicit N/A checks. |
| MEDIUM | Per-agent timer ends before checks/trace/artifact persistence; telemetry.py, run_task.py | Per-scenario measures apply+connector setup to snapshot, but worker import/init occur outside. Global time includes both agents and evaluator, cannot serve as per-agent full workflow time. Add declared spans and lifecycle boundary; separate grading cost/time. |
| MEDIUM | No code/evaluator/config hash or result-to-check hash binding; run_task.py | Scenario hashes exist, versions are labels; add commit/dirty digest, evaluator/trace/result bindings. |
| MEDIUM | Structured sanitizer misses free-text and keys like private_key, and redacts token-count fields; schemas/trace.py | Use logging allowlist and canary tests, preserve numeric input_tokens/output_tokens. Current synthetic fixture-only restriction is sensible. |
| LOW | All baseline first, then candidate; no repetitions/holdout | AB/BA + paired repetitions and grouped split when actual agents introduced; tiny runtime makes present timing comparisons uninformative. |

No production-critical release claim is justified by 70/70 alone. Do not rewrite P0 wholesale: retain contracts, reference policy as harness fixture, mock behavior and current negative tests while tightening boundaries incrementally.

## Evaluator leakage risks
Expected outcome is not directly included in TaskContext: good. However expected answer remains in public same-process scenario JSON; candidate can read filesystem/import runner or inspect frames. Connector exposes ALL fixture data without tool calls. It also exposes mutable approval, event log and receipts. Thus **no independent evaluator boundary** against a candidate that inspects/mutates internals. This is disclosed in README and not evidence that the shipped agents cheat. No held-out evaluation exists yet. Keep public development expectations public; hide only release evaluator data in separate storage/process with enforced access restrictions.

## Baseline fairness
Inputs and tool permissions are equal; fixture dictionaries are deep-copied. No intentional baseline handicap. Current equality is fair for plumbing but neither adapter is a minimal viable LLM MUSE: both execute hardcoded synthetic policy. Keep this policy as reference/fake agent for harness tests. Future honest baseline must use same model/config/tool budgets and capable basic prompting; candidate-only expected labels and case-ID branches prohibited. Verify equality through fixture hashes and initial-state snapshots; current unit test compares outputs/actions rather than directly proving all fixture values match.

## Candidate meaningfulness
Behavioral difference: **none**. Both use ReferencePolicy.apply unchanged. Candidate version label is not an architecture improvement. Current suite does not test free planning, inference, retry adaptation or evidence synthesis. Replacing this stub requires a real adapter under frozen evaluator; no requirement that it win every case. Negative result should remain reportable.

## Proposed differentiating scenarios
These are proposals, not files added or runnable tests. Use the same fair baseline tools/model and unknown variants; no scripted desired failure.

| ID | Purpose / expected behavior | Legitimate candidate capability | Independent oracle |
|---|---|---|---|
| D01 | Incomplete conversion lag data: investigate or ask precise missing window; no causal claim | evidence sufficiency check | requested missing field, UNKNOWN classification, no write |
| D02 | Conflicting Ads gross revenue and SellerOS net revenue/returns | source/time/currency normalization | independent gross/net reconciliation with exact money |
| D03 | Budget proposal approval for 120 then args change to 150 | approval-bound action protocol | second approval required, no unauthorized mutation |
| D04 | API accepts asynchronous change, later returns failed | verification and pending-state handling | never report executed before confirmed state |
| D05 | Campaign anomaly requires placement breakdown then sales/returns check | multi-step routing driven by returned evidence | correct scoped query chain and supported decision, equivalent paths allowed |
| D06 | Old creative with CTR decline but simultaneous placement-mix change | fact/hypothesis separation and competing hypotheses | observed metrics FACT, fatigue HYPOTHESIS, explicit validation plan |
| D07 | First read 429; a write commits but its response is lost | bounded read retry + reconcile ambiguous write | successful read recovery, exactly one business effect, receipt reconciliation |
| D08 | Proposed spend reduction saves cost but eliminates high-margin sales | downstream margin-aware outcome | synthetic state transition/oracle computes profit impact, no reward for CPC alone |

Baseline/candidate results for D01–D08: NOT RUN. PASS/FAIL: NOT RUN. These cases expose useful capabilities but do not presume candidate success. Do not add all cases now: choose D02/D03/D04 first after tightening output contract; financial fixture can stay fully synthetic.

## Checks and metrics
Reproduced checks: run_completed, expected_outcome, evidence_grounding, correct_tools, no_fabricated_execution, approval_policy, idempotency all PASS on ten existing cases for both adapters. Financial correctness, runtime output contract and regression-as-release-check are NOT IMPLEMENTED. Unit suite separately passes 17 tests.

Adversarial probes (read-only review execution; production modules unchanged): false semantic claim passes grounding; free-text fabricated execution not detected; mutable approval bypass succeeds; inadmissible score retains numeric aggregate. These are explicit review failures, not changes to published scenario results.

Existing baseline/candidate task status and tool checks: 10/10; evidence payload-match checks: 10/10; structured fabricated-action/approval/idempotency failures: 0 within shipped cases. Semantic grounding/action safety and restart idempotency NOT ESTABLISHED. No model cost or inference metrics; wall-clock and call counts are machine/run-specific and are not evidence of candidate superiority. No benchmark performance claim made in this review.

## Files added
Only docs/REPO_AUDIT.md, docs/MUSE_HARNESS_SPEC.md, docs/SCENARIO_SCHEMA.md, docs/EVALUATION_CONTRACT.md, docs/IMPLEMENTATION_PLAN.md and docs/ASTRA_REVIEW_REPORT.md. These are proposal documents and review; no agent/harness/test/scenario files changed.

## Git
Target branch: astra/harness-design. Base: 861980b0fd2e7e535ba982993b4d63312a61af76. One docs-only review commit intended; resulting commit SHA and confirmed push status are supplied in the final response (a commit cannot contain its own SHA). No main merge.

## Next Codex task
1. Separate candidate worker from trusted connector/evaluator, enforce timeout and narrow RPC; add approval/event mutation and expected-file access negative tests. Keep current reference policy for plumbing tests.
2. Make critical-gate failures DISQUALIFIED with aggregate=null; require mandatory correctness before efficiency credit; preserve raw metrics.
3. Introduce typed material claims/actions and exact source-field/value/time/currency predicates; derive displayed completion from verified receipts, not unchecked prose.
4. Bind approvals to args/resource/actor/expiry and persist operation-scoped idempotency; test restart/lost response without duplicate mutation.
5. Integrate honest model-agent baseline and real candidate behind unchanged contract, then implement a small D02/D03/D04 subset, preserving equal tools/data/budgets and reporting paired outcomes honestly.

## COPY-PASTE CONTEXT FOR MAIN AGENT
CURRENT STATE: katarssys/MUSE main 861980b0fd2e7e535ba982993b4d63312a61af76 reviewed; 17/17 unit tests reproduced; 10 scenarios × 7 checks = 70/70 per side. Both adapters share ReferencePolicy, no model; no candidate advantage demonstrated. Six documentation files added on astra/harness-design; implementation untouched.
CRITICAL GAPS: same-process mutable connector allows approval/ledger tampering and fixture inspection; semantic false claims/free-text fabricated execution not evaluated; numerical scores remain on inadmissible runs; idempotency resets on each run; approvals unscoped. README discloses trusted synthetic limitations.
NEXT P0: tighten trust/output/gate boundary using existing modules and reference fixtures, then real equal-budget baseline/candidate adapters and 2–3 discriminating cases. No new repo, no frontend, no live Meta API, no main merge.

Следующему агенту следует начать с: защиты границы candidate → connector/evaluator и негативного теста, запрещающего candidate менять approval или журнал событий.
