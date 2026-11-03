# MUSE — verification and control layer for agentic systems

**Meta made agents capable of acting. MUSE makes those actions verifiable.**

MUSE is a verification/control layer for tool-using agents. It sits between model
intent and external state, enforcing evidence integrity, scoped approvals,
idempotent execution and authoritative post-action verification.

The core idea is simple:

```text
Evidence → Consistency → Policy → Action → Receipt → Readback → Verified State
```

MUSE is not a replacement for an agent model. It is the layer that helps prevent
an otherwise capable agent from turning incomplete evidence, wrong scope,
accepted-but-not-executed writes, or stale state into a confident final answer.

## Hackathon result

On the current public five-case live model benchmark, using the same configured
provider/model client, tools, scenarios, limits and frozen evaluator for both sides:

| System | Passed | Hard failures |
| --- | ---: | ---: |
| Baseline agent | 0/5 | 0 |
| MUSE agent | **5/5** | **0** |

Latest validated live run:

```text
muse_eval/runs/model-9e5ef14561cf474691a3a6da9d192d00
```

The run executed all five selected cases with a configured Meta Model API client and
`muse-spark-1.3`. The manifest reports `actually_connected=true`.
The harness still records `model_family_verified=false`, so it does **not** claim
independent cryptographic or provider-side verification of model-family authenticity.

Current regression status:

```text
176 tests
176 passed
0 failed
0 skipped
```

The frozen evaluator remains pinned to:

```text
da2ff0b1d7753ba0918f77b1a8cf3ff451a24434
```

## Four-domain universality proof

The same verification engine is exercised across four very different domains:

| Domain | Synthetic proof |
| --- | --- |
| Marketing | evidence completeness, gross/net reconciliation, exact campaign budget approval, readback |
| E-commerce | effective availability, supplier readiness, duplicate reorder prevention, fulfillment verification |
| DevOps | scoped deployment approval, idempotency, accepted deployment vs health readback |
| Mechanical Engineering | multi-source evidence, operating envelope, accepted parameter change vs sensor readback |

A fifth synthetic Inventory contract is used as a generic extension proof.

All of them use the same `DomainContract` / `SyntheticWorkflow` machinery. The
generic engine does not branch on domain names.

```text
                         MUSE CORE
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
    Evidence             Policy            Verification
   requirements       + approvals         + readback
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
       ┌───────────┬────────┼─────────┬────────────┐
       │           │        │         │            │
   Marketing   E-commerce DevOps  Mechanical   Inventory
```

The shared domain contract supports:

- required evidence capabilities;
- typed evidence fields;
- compatibility dimensions such as basis, currency, unit, period and scope;
- declarative linear cross-source relationships;
- exact resource/action/parameter/value approval binding;
- numeric operating envelopes;
- idempotency keys and conflict detection;
- accepted/pending state distinct from verified state;
- receipt/resource/path-correlated authoritative readback;
- latest observation wins.

## Why MUSE exists

Tool-using agents can be impressive while still failing at the workflow level.
Typical failure modes include:

- concluding before a required downstream source is checked;
- comparing semantically incompatible metrics;
- serializing only part of the evidence needed to support a conclusion;
- acting on the wrong target or stale approval scope;
- treating an accepted write as completed;
- missing asynchronous failure after submission;
- replaying the same side effect;
- trusting an earlier successful observation after later state has failed.

MUSE turns those failure classes into explicit workflow invariants instead of
leaving them entirely to model prose.

## Live model architecture

The paired benchmark uses the same provider/model configuration and tool surface for
both adapters.

```text
                 SAME MODEL / SAME TOOLS
                          │
              ┌───────────┴───────────┐
              │                       │
        Baseline adapter          MUSE adapter
              │                       │
              └───────────┬───────────┘
                          │
                  Frozen P0.2 evaluator
```

The baseline receives the shared public tool/output contract. MUSE receives the
same contract plus explicit evidence/action workflow guidance covering evidence
acquisition, source compatibility, approval scope, action lifecycle and readback.

The five live cases cover:

1. missing downstream evidence;
2. conflicting campaign and sales evidence;
3. gross-vs-net revenue reconciliation;
4. approval scope change;
5. accepted write followed by failed verification.

The latest validated result is baseline **0/5** vs MUSE **5/5**. This is a controlled,
public, synthetic development benchmark, not a claim of universal model superiority.

## Built during the hackathon

Hackathon work includes:

- provider-neutral live model adapters;
- Meta Model API benchmark integration;
- MUSE evidence/action workflow prompt layer;
- structural orchestration guards;
- paired live benchmark driver;
- strict evidence, approval and readback handling;
- shared domain contract;
- Marketing proof;
- E-commerce proof;
- DevOps proof;
- Mechanical Engineering proof;
- Inventory generic-extension proof;
- regression tests for the above.

The original P0.2 deterministic evaluator is retained as the frozen verification
foundation rather than silently rewritten to favor the new model-backed path.

## What is real vs synthetic

Implemented and demonstrated:

- live model calls through the configured provider;
- frozen evaluator-backed five-case paired benchmark;
- deterministic synthetic domain workflows;
- approval/idempotency/readback verification semantics.

Not implemented:

- production Meta Ads integration;
- Shopify/Kaspi/Ozon/Wildberries integration;
- Kubernetes or cloud control;
- PLC/SCADA/sensor control;
- production IAM;
- durable distributed ledger;
- concurrency/crash recovery;
- real industrial safety certification.

The Mechanical proof uses synthetic observations only and must not be interpreted
as authorization to control real equipment.

## Demo UI

A static hackathon demo is available under `demo/`. It visualizes the same MUSE
verification concepts used by the tested domain proofs:

- Marketing
- E-commerce
- DevOps
- Mechanical Engineering

The demo shows the shared flow:

```text
Evidence → Consistency → Policy → Action → Receipt → Readback → Verdict
```

Run it locally from the repository root:

```powershell
& "C:\Users\katya\AppData\Local\Python\bin\python.exe" -m http.server 8080 -d demo
```

Then open:

```text
http://localhost:8080
```

The UI is intentionally static and dependency-free (`HTML + CSS + JS`) so it can
be used reliably for the hackathon demo/video without adding a new frontend build
pipeline. It does not replace the benchmark or synthetic workflow engine; it presents
the verified behaviors in a judge-friendly interface.

## Quick validation

Python 3.10+.

```sh
python -m unittest discover -s muse_eval/tests -v
python -m muse_eval.harness.run_task
python -m muse_eval.agents.model.run_benchmark
```

The live benchmark requires valid provider/model configuration and credentials.
Generated runs are stored under `muse_eval/runs/` and are ignored by Git.

## P0.2 deterministic foundation

The deterministic harness remains the trusted evaluator foundation. Its original
baseline/candidate result is baseline **13/14**, candidate **14/14**, with zero hard
failures. No new benchmark scenarios were added to create the model comparison.

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
[agents/model](muse_eval/agents/model/README.md).

Current connected live benchmark status on `codex/muse-model-adapter-p1`:

- full unit suite: **142/142 PASS**;
- paired five-case live run: baseline **0/5 PASS**, MUSE **5/5 PASS**;
- MUSE hard failures: **0**;
- all five MUSE cases passed run completion, expected outcome, grounding, tool
  correctness, fabricated-execution safety, approval policy, idempotency, target
  correctness and required-evidence checks;
- frozen P0.2 evaluator/scenarios/connectors/schemas/deterministic agents remain
  byte-checked and unchanged by the model benchmark driver.

The connected run used the same configured provider/model client for baseline and
MUSE. Provider/model identity is recorded as declared configuration in the generated
manifest; independent model-family authenticity is still **not** claimed by the
harness. Generated run artifacts stay under ignored `muse_eval/runs/`.
