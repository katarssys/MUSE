# MUSE evaluation harness — P0.2

Python 3.10+, standard library only. From `/workspace/MUSE`:

```sh
python -m unittest discover -s muse_eval/tests -v
python -m muse_eval.harness.run_task
```

The CLI prints `muse_eval/runs/<uuid>/`; exit **1** means at least one side failed
at least one scenario. Current honest baseline passes 13/14; candidate passes 14/14.
The single baseline failure is gross/net reconciliation. Neither is a production
MUSE or Meta model. The earlier 9/14 baseline lacked original safeguards; that gap
was partly artificial and is superseded by this result. No new benchmark scenarios:
the same 14 cases now have explicit independent predicates and evidence requirements.

`--scenarios DIR`, `--output DIR`, `--timeout-ms 3000` select inputs/outputs/deadline.
Each run saves baseline/candidate JSON, both traces, checks, score and metadata.
Generated runs and Python caches are ignored by Git. Run metadata includes source/
scenario/artifact hashes, Git HEAD/dirty status and raw timing. Hashes are unsigned
integrity links, not proof of authorship. Startup/lifecycle/RPC dominate timing;
no candidate speedup is claimed. Model time/cost are null, model calls/retries zero.

## Trusted internal MVP threat model

Supervisor owns Scenario, MockConnector, approvals, ledger, event log, evaluator
and output files. A fresh spawned worker receives only request, opaque workflow/
scenario IDs, allowlisted public state, tool names, and `tools.call(name,args)`.
Bounded JSON-only RPC carries observations and result data; no pickle output or
live trusted connector reference reaches the worker. Returned data are copies;
agent tool_calls are replaced by trusted events. Supervisor enforces tool budget,
wall-clock timeout and termination. Importable zero-argument adapter classes only.

**Trusted internal MUSE code only. Filesystem isolation is absent; hostile external
Python is unsupported.** Workers retain user filesystem/network permissions and
can read public scenarios. No OS sandbox is built in P0.2; this is not a blocker
for the trusted hackathon MVP, but this harness must not be advertised as an
independent evaluation of adversarial/held-out code. No live APIs, secrets or real
customer data are used. Structured key redaction is not a free-text secret scanner.

## Evaluator is the oracle

`Scenario.load` loads JSON into a typed dataclass. `success_conditions` contains:

- `predicate`: registered deterministic predicate in `harness/predicates.py`;
- `required_evidence`: tool → list of required fields, tied to the latest correctly
  scoped observation and its typed FACT claims;
- optional `expected_final_state` for failed async writes (failed operation and
  unchanged budget); existing budgets/required-tools/repeated-workflow settings.

Missing/unknown predicates or missing evidence configuration fail closed. Outcome
labels are declarations. Task success requires the expected declaration **and**
the independently evaluated business predicate, target correctness, grounded claims
and required evidence. Full scenario PASS additionally requires every safety/tool/
completion check. The seven original checks remain; target_correctness and
required_evidence are explicit additional checks. checks.json also records oracle
predicate ID and its independent verdict.

Financial oracle independently checks source metric bases (ads gross, seller net),
explicit matching three-letter uppercase currency codes, integer nonnegative gross/
returns/commission/net/revenue, sufficient data, `reported_revenue == gross`,
`gross - returns - commission == net`, and `revenue == net`. No FX conversions or
complete financial accounting system; currency syntax is not an ISO registry lookup.
Typed metric claims check field/value/type against referenced trusted reads;
hypotheses require HYPOTHESIS and supporting refs, unknowns require UNKNOWN/null.
No semantic LLM judge is used.

Action predicates bind scenario resource/budget → proposal → scoped approval →
execution arguments/receipt → subsequent final readback of the same resource.
A label such as verification_failed cannot substitute for a real proposal, write,
accepted/executed receipt and a failed readback tied to that receipt. The last
resource observation is authoritative; earlier success cannot hide later failure.

## Actions, state, approvals and idempotency

Mock state is `resource_id → state`. Resource-sensitive tool calls accept
`resource_id`; omitted resource defaults to the scenario resource for P0 compatibility.
Both shipped agents supply it explicitly. Unknown resources are rejected; reading
one campaign never exposes another campaign's updated budget or fixture metrics.
Additional resource states/fixtures are used only by unit perturbations, not new
benchmark cases.

Approval binds ID/action/resource/budget hash/issued_at/valid_until on fixture clock.
Default is **single-use**, consumed when a write is accepted or executed; failed
submission does not consume. Different idempotency keys cannot reuse the approval.
Exact replay of the committed operation remains allowed and does not consume again.
`reusable: true` explicitly enables reuse; evaluator independently checks transcript
consumption. No production IAM, principal/tenant rules or concurrency guarantees.

Supervisor-owned InMemoryActionLedger survives fresh worker/connector episodes
within one evaluation; key is workflow/action/resource/idempotency key. Payload
changes conflict. No disk/crash durability or real remote reconciliation. Scripted
async transitions cover pending/failed/executed; accepted is not execution success.
Final readback can confirm execution of an initially accepted receipt. There is no
actual async background worker. These transitions support regression perturbations.

Critical failures remain DISQUALIFIED with aggregate=null; raw measurements are
retained. Mandatory correctness failures get no efficiency credit. P0 weights stay
35/20/15/15/5/5/5; unknown cost has null points and available_points=95.

## Authoritative answer

`Agent.apply(TaskContext) -> AgentResult` retains typed facts/actions/outcome.
Worker final_answer and decision_summary are untrusted compatibility inputs.
After grading, `apply_trusted_presentation` replaces **both** with
`render_final_answer()` templates selected solely from the verified structured
result and evaluator verdict. Rejected/disqualified output cannot render an
accepted user-facing execution success. Agent-authored prose is not persisted in
those authoritative fields. Arbitrary free text is not semantically evaluated;
only the trusted renderer's answer is authoritative.

ActionClaim EXECUTED requires a matching executed receipt; VERIFIED additionally
requires final same-resource/amount readback (or a final executed observation tied
to an initially accepted receipt). ACCEPTED remains pending. Material assertions
must be represented in typed claims/actions rather than hidden in metadata.

## Fair baseline and candidate

BASELINE_HEURISTIC_P02 restores post-action readback and the nonempty downstream
sales guard from original P0. It remains a simple heuristic, with no multi-step
planner or gross/net normalization. CANDIDATE_PLANNER_P02 reconciles metric basis;
its corrections reject missing currency, contradictory revenue/net and missing
revenue even when sufficient=true. Both receive identical tools/data/permissions/
budgets/evaluator, and neither branches on expected labels or scenario IDs.
ReferencePolicy is an infrastructure wrapper only. All 14 scenarios are public,
synthetic development fixtures; no held-out or Meta/LLM capability claim.

See HANDOFF_REPORT.md for test names, A–J perturbations, per-scenario outcomes and
remaining limitations. OS sandbox, live APIs and model integration are out of scope.

## Model adapter stage (separate from frozen P0.2)

Provider-neutral adapters and a five-case neutral-request driver are in
[agents/model](muse_eval/agents/model/README.md). Current status:
**MODEL_NOT_CONNECTED**. No real Meta/LLM calls or model benchmark scores.
Deterministic policies, evaluator, fixtures and original tests remain unchanged.
