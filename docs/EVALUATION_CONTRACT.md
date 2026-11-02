# Evaluation contract v1
Normative design; no runtime implementation.

## Trusted artifacts
Per run: manifest.json, observations.jsonl (sanitized), trace.jsonl, receipts.jsonl, initial/final protected state snapshots, agent_result.json, usage.json, result.json, checks.json, score.json, regression.junit.xml. Public audit export is a redacted projection, never unrestricted fixture/evidence dump. Atomic writes followed by immutable freeze; interrupted output is explicit incomplete status.

manifest: run_id/pair_id/episode_id/operation_id; baseline/candidate code commit and dirty-tree digest; evaluator commit; scenario/schema/fixture/policy hashes; model ID/revision/provider/config/prompt hash; tool schemas/config versions; seed; clock; environment/package lock digest; cache mode; pricing version; feature flags; start/end timestamps. No credential values or raw environment.

result.json: schema_version, manifest_hash, completion_status, raw_metrics, per_requirement outcomes, artifact hashes, infrastructure errors. checks.json: result_sha256, evaluator_version, scenario_hash, trace_hash, regression_report_hash, check list {id,status,severity,reason,evidence_refs}. score.json: checks_sha256, eligibility, disqualification_reasons, dimension_scores, aggregate or null, scoring_version, coverage. Digest mismatch fails closed.

## Trace event
```json
{
  "schema_version":"1.0.0", "event_id":"ev-01", "run_id":"run-01",
  "sequence":1, "span_id":"sp-01", "parent_span_id":null,
  "timestamp":"2026-11-02T00:00:00Z", "monotonic_offset_ms":10,
  "event_type":"tool.result", "producer":"trusted_broker",
  "tool_call_id":"tc-01", "evidence_refs":["e-01"],
  "approval_state":"not_required", "receipt_id":null,
  "safe_summary":"Read daily campaign totals", "status":"ok"
}
```
Event types cover observation, evidence registration, tool selection/call/result, decision_summary, approval request/decision, execution/receipt, verification, outcome, error, retry, model usage. No private chain-of-thought. Decision summary is concise action justification with evidence IDs, not internal reasoning transcript. Broker events authoritative; candidate-authored summaries labelled untrusted_agent. Event sequence and causal IDs validated; parent monotonic clock measures duration across processes.

## Evidence and output
AgentResult.claims require id, kind FACT/SIGNAL/INFERENCE/HYPOTHESIS/UNKNOWN, text, structured value/unit/currency/as_of where relevant, evidence_refs, uncertainty and scope. Actions require operation_id, tool_call_id, status, receipt_id, verification refs. User-visible prose checked as well as structured claims. Completed requires verified outcome, not just a successful API response. Approval-handoff/clarification are expected outcomes only when scenario allows them.

Evidence reference must resolve to tool-observed authorized source in same tenant/run or explicitly allowed production memory. Source string existing is insufficient: value, time window, units and claim entailment checked. Contradictory evidence cannot be ignored. Absence of available facts can justify UNKNOWN, not invented values.

## Error semantics and tests
ToolResult statuses ok/denied/transient_error/permanent_error/pending/unknown; execution statuses separate. Retry budgets finite. Output schema rejects NaN/Infinity/bool-as-money/unresolved refs. Required regression inventory versioned; JUnit report must come from trusted CI evaluator checkout, no required skips allowed. No parsing 'N passed' stdout.

Release checks include malicious worker attempts to read expected/, write checks.json, use raw network, forge broker receipt; financial rounding/refund invariants; approval expiry/args mutation/races; crash recovery/idempotency; replay miss; prompt injection; secret leakage in exceptions/logs; model judge disagreement cases. These are meaningful boundary tests, not implementation mirrors.
