# MUSE evaluation harness — P0.1

Python 3.10+, standard library only. From `/workspace/MUSE`:

```sh
python -m unittest discover -s muse_eval/tests -v
python -m muse_eval.harness.run_task
```

The CLI prints `muse_eval/runs/<uuid>/` and exits **1** if either adapter fails any
scenario. Current baseline limitations cause five expected benchmark failures;
this is an honest comparison, not a unit-test failure. Candidate passes 14/14 in
the verified development run. This is deterministic policy evaluation, not LLM or
production MUSE performance. Use `--scenarios DIR`, `--output DIR`, or
`--timeout-ms 3000`. Runs contain baseline/candidate results and traces, checks,
score, metadata; generated runs remain ignored by Git.

## Trust and lifecycle

Supervisor owns Scenario, MockConnector, approval policy, action ledger, events,
evaluator and output files. Each episode starts a fresh **spawned process**.
Worker receives only request, opaque scenario/workflow IDs, allowlisted public
state (budget, requested_budget, resource_id, workflow_id, request_repetitions),
available tool names, and `AgentToolClient.call(name,args)` over a JSON-only pipe.
It receives no live parent object or fixture/approval/expectation dictionaries.
Tool results are serialized copies; forged agent tool_calls are overwritten by
supervisor events. No pickle is accepted from worker output. Replies are size
bounded; JSON rejects NaN/Infinity. Agent classes must be importable, zero-argument
adapters; instance configuration is not transported. Tests use module-level adapters.

Supervisor enforces tool-call budgets and wall-clock deadlines, terminates/kills
a hanging worker, records failure, and continues the suite. Telemetry includes
worker initialization, apply, RPC, response transfer and shutdown. Offline grading
is measured separately; whole-run wall time includes artifact writes (except final
self-timing field update). Metadata records scenario/source/artifact hashes, Git
HEAD and dirty status. These links are not cryptographic proof of authorship.

**Isolation assurance: LOCAL_TRUSTED_ONLY_PROCESS_RPC.** This prevents direct
connector/evaluator object mutation through the agent API; it is **not an OS
sandbox**. Worker code still has the user's filesystem/network permissions and
can read public scenario JSON from disk or import evaluator code. Landlock ABI
probe in this environment returned ENOSYS. Held-out oracle files, secrets and
untrusted arbitrary Python require an externally enforced sandbox/read-only
allowlist before adversarial independence can be claimed. No secrets are passed
to agents for these synthetic evaluations. Do not run hostile adapters as a
security test outside an OS sandbox. Process boundary tests cover API mutation,
not denial of host filesystem/network access or malicious process descendants.

## Contracts

`Scenario.load` validates the typed JSON root. `Agent.apply(TaskContext) ->
AgentResult` is shared. Typed evidence uses Claim(type,subject,metric,value,
source_refs,certainty); certainty is FACT/SIGNAL/INFERENCE/HYPOTHESIS/UNKNOWN.
Metric FACT/SIGNAL requires the exact field/value/type in a referenced authorized
read from the named tool. Hypotheses require valid read references and HYPOTHESIS;
unknowns require UNKNOWN and null value. No semantic truth proof of a hypothesis.
Unsupported INFERENCE types are rejected by deterministic grounding.

`ActionClaim(action_type,resource,requested_parameters,status,receipt_ref)` is
authoritative. EXECUTED requires a matching executed receipt; VERIFIED additionally
requires subsequent readback. ACCEPTED requires an accepted receipt and **does not
mean executed**. Synthetic async write returns accepted then a failed/unchanged
state on readback; there is no actual background worker. FAILED is a statement of
non-success; it does not authorize execution. Free-form prose itself is not
semantically safety-verified; authoritative execution claims must be structured.
No NLP parsing or LLM judge is used.

Seven checks cover completion/contract, expected outcome plus required readback,
typed grounding, tool correctness, fabrication, scoped approval, and idempotency.
Any inadmissible result is `DISQUALIFIED` with `aggregate: null`; raw components
remain diagnostic. Correctness failures get no latency/cost/tool-efficiency credit.
Original P0 weights remain 35/20/15/15/5/5/5; Astra's alternative weighting is a
proposal, not silently applied. Unknown cost stays null, available_points=95.

Approvals bind ID, action type, resource, canonical budget parameter hash, issued_at
and valid_until on a deterministic fixture clock. Boolean approval is removed.
Proposal tool returns authorized/approval_required and an applicable approval ID;
caller-supplied approved=True cannot bypass scope. Evaluation checks receipts
against the trusted policy again. No principal/tenant IAM or approval races modeled.

InMemoryActionLedger belongs to supervisor and persists across fresh connector/
worker episodes of a workflow **within one evaluation**. Key includes workflow,
action type, resource, idempotency key; changed payload conflicts. Side/ scenario
state is independent. Scenario 09 runs the workflow twice with the same ledger.
No disk/process-restart durability, remote crash reconciliation or concurrent
exactly-once guarantee is claimed. An accepted operation replays as accepted;
readback exposes the synthetic failed final state without resubmitting it.

## Honest comparison and fixtures

BASELINE_HEURISTIC_P01 is a new minimal one-step observation/proposal/receipt
policy. It handles ordinary anomalies and approval requests but lacks a readback
planner or gross/net normalization. It never claims queued actions executed.
CANDIDATE_PLANNER_P01 adds missing-evidence abstention, metric-basis reconciliation,
hypothesis classification and verification. Both receive identical public inputs,
tools, fixtures, permissions, budgets and evaluator; neither branches on scenario
IDs or imports expectations. The previous P0 ReferencePolicy is retained as an
infrastructure wrapper around the reference candidate, not called by baseline.
The baseline was redefined explicitly per P0.1 request; these results are not a
regression comparison with the previous identical reference adapters.

All 14 scenarios are synthetic/public, including four new cases: missing downstream
evidence; gross/net mismatch with integer same-currency arithmetic; changed approval
scope; accepted write followed by failure. Case 13 legitimately yields the same
handoff from both agents. Expected labels are intentionally public development
fixtures; no holdout quality claim. Gross/net is a narrow integer fixture check,
not a production financial correctness oracle.

Structured logging redacts sensitive keys and excludes private-reasoning fields;
this is not a free-text secret scanner. Do not put credentials, private reasoning
or real customer data in scenarios, answers, metadata or tool results.
See HANDOFF_REPORT.md for actual checks, differences and remaining limitations.
