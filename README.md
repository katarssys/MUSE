# MUSE evaluation harness — P0

Python 3.10+; standard library only. From `/workspace/MUSE`:

```sh
python -m muse_eval.harness.run_task
python -m unittest discover -s muse_eval/tests -v
```

The CLI runs ten synthetic JSON scenarios, exits nonzero if any check fails, and prints
its output directory. `--scenarios DIR` and `--output DIR` select input/output roots.
Each run creates baseline.json, candidate.json, trace_baseline.json,
trace_candidate.json, checks.json, score.json, metadata.json under
`muse_eval/runs/<uuid>/`. Results are ignored by Git.

## Contracts

`Scenario.load(path)` loads a typed dataclass from JSON (no YAML dependency).
Fixtures are embedded in `fixture_data`; expectations stay out of TaskContext.
`Agent.apply(TaskContext) -> AgentResult` is shared by both adapters. Supply replacements
via `run(agents={"baseline": adapter, "candidate": adapter})`.
Each scenario/adapter gets a fresh mock connector, ledger and telemetry. Isolation is
in-process state isolation, not an OS sandbox for untrusted code. Agents receive a
connector object; they are trusted not to inspect its implementation or mutate its ledger.

`Connector.call(name, args) -> ToolResult` records calls, latency, evidence references,
and results. Approval comes only from scenario state, never tool arguments. Successful
executions return receipts; idempotent replays reuse receipts. Verification reads observe
the actual updated mock budget. All seven requested mock tools are implemented.

Evidence entries use `{claim, data, references}` with references such as `tool:1`.
Grounding checks that data exactly matches a successful read. `actions` is a list of
execution receipts; `outcome` is a structured status code. Checks validate these fields,
not arbitrary natural-language semantics. A future natural-language agent must expose
all material claims/actions through these fields; free-text hallucinations are not
semantically judged by this P0 implementation. The two shipped adapters return only
status codes as final answers and copy observations into evidence. A stale creative is
a hypothesis; no causal proof is claimed.

Seven checks cover completion, expected status plus required post-execution verification,
evidence, allowed/required tools, execution receipts, approval, and duplicate actions.
Critical violations make a result inadmissible regardless of aggregate points. Outcome
quality currently reuses deterministic success/safety checks; it is not an independent
semantic quality judge. Weights are isolated in `harness/score.py`.
Unknown cost is null, with cost points null and available_points=95; no fake zero-cost
credit or extrapolated 100-point score. Scores use explicit latency/tool budgets.
Per-agent timing measures the entire apply call including connector activity, not just
model latency. Run wall-clock also includes loading, checks and artifact writes.
Model time and cost are null; model calls and retries are zero for these adapters.

## Status and boundaries

Both adapters share a reasonable deterministic reference policy: BASELINE_STUB and
CANDIDATE_REFERENCE. Their equality is intentional, not evidence of candidate improvement.
No model, live integrations, external services, customer data, or production runtime.
No research repositories were needed for this implementation.

Synthetic fixtures contain no secrets. Serialization recursively redacts sensitive keys
and drops structured private-reasoning fields. This is not a free-text secret scanner:
do not supply credentials, private reasoning, or sensitive customer text in scenarios,
answers, metadata, exceptions or tool results. Untrusted production adapters require
an explicit logging allowlist and an isolation boundary before use.

To add a scenario, copy an existing JSON, choose a unique id and define explicit
expected_outcome and success_conditions. To replace adapters, implement the same apply
contract; add negative regression tests before extending action/claim formats.
Do not create a Git worktree for routine cloud tasks: the current checkout is isolated.
