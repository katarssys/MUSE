# P1 model adapters — MODEL_NOT_CONNECTED

This is an unconnected provider-neutral adapter scaffold, not a Meta benchmark.
The configured environment has no model endpoint, model ID, model credential,
outbound identity or local inference runtime. No Meta model was selected or invoked.
Existing deterministic agents remain untouched regression fixtures.

From repository root:

```sh
python -m unittest discover -s muse_eval/tests -v
python -m muse_eval.agents.model.run_benchmark
```

Without configuration the second command writes a `model-<uuid>/manifest.json`
and summary under ignored `muse_eval/runs/`, prints MODEL_NOT_CONNECTED, exits 2,
and creates no synthetic scores. There are five selected cases, zero executed
model benchmark cases. Unit-test scripted responses and mocked HTTP are not Meta calls.

## Connection prerequisites

A real provider/runtime must first be identified and its actual available Meta/Llama
model and protocol support verified. This code supplies no invented default endpoint,
model name or credentials. The optional ChatCompletionsClient is a standard protocol
template, tested with mocked HTTP only; real provider compatibility is NOT VERIFIED.
It currently requires JSON-schema chat response support. Unsupported schemas produce
an explicit provider error; no silent alternate model or protocol fallback.

Configuration names (values entered securely in environment settings):

- MUSE_MODEL_PROVIDER: actual selected provider name.
- MUSE_MODEL_ID: exact available Meta/Llama model revision/ID.
- MUSE_MODEL_FAMILY: meta_llama; declared selection, not independent authenticity proof.
- MUSE_MODEL_ENDPOINT: explicit HTTPS chat-completions URL from that provider's docs.
  No query, fragment or embedded user credentials; no endpoint guessing/appending paths.
- MUSE_MODEL_API_KEY: credential binding for that endpoint, never in source or chat.

The destination must be allowed by cloud networking. No domain/secret requirement
was added because the provider/destination is not yet known. Reuse existing secure
bindings when supplied; preserve proxy and CA trust. Redirects are rejected, TLS
verification remains enabled. Do not use a placeholder provider as a real Meta run.

## Agent contract and fairness

ModelClient.generate(messages,schema,timeout_s) returns text, optional structured
output, nullable usage/cost, latency and safe provider metadata. Provider-specific
HTTP code stays in provider.py. Zero-argument adapters instantiate the same config
from environment inside the existing frozen spawned worker; injected clients are
supported only for direct unit tests. Both adapters share the same parser/schema,
client, model selection, temperature, tools and budgets. No second candidate model.

MetaBaselineAgent uses a normal helpful tool-use prompt with accurate structured
reporting. MuseModelAgent adds an explicit evidence/action workflow prompt:
classification, missing-evidence checks, routing, scope-aware proposal, verification
and uncertainty. Both can use all allowed tools and verify writes. The difference
is currently prompt-level workflow scaffolding in a shared loop, not an integrated
production MUSE runtime. No measured architecture advantage is established.

Neither adapter imports scenarios, predicates, fixtures or evaluator expectations.
Available tool descriptions and outcome-code vocabulary are a shared public output
contract, not scenario-specific rules or expected labels. Public context is allowlisted.
Workflow/receipt IDs are aliased to opaque identifiers because public fixture IDs
contain scenario names. Known receipt aliases are decoded on return; claims are not
repaired or augmented from expected answers. Unknown aliases/false claims still fail
the unchanged evaluator. Private reasoning and raw model responses are never exported.

Parser requires one tool decision or final structured result; no markdown repair,
no automatic action, no fabricated receipts. Tool observations feed the next model
turn. Final output is validated against frozen AgentResult and passed to the frozen
checks/renderer. Model-generated metadata cannot replace measured usage.

Equal defaults: temperature=0, max_model_calls=8, max_tool_calls=8,
max_output_tokens=2048 per call, max_context_chars=24000, workflow_timeout_ms=60000,
per-request timeout <=15s and remaining deadline. Context is character-bounded
without a provider tokenizer; exact input tokens are reported only when provider
usage exists. Over-budget context fails; evidence is not silently truncated.
Model/tool/timeout/parser errors return explicit status and fail evaluation.
No automatic retries; partial/missing usage totals stay null, never false zero.

## Benchmark and telemetry

Five cases: 11 missing evidence, 04 conflict, 12 gross/net, 13 approval scope,
14 async failure. Neutral user_request variants exist only in memory and manifest.
Original fixture_data, approvals, permissions and success_conditions are unchanged
and identical for both sides. The driver checks every frozen harness/schema/connector/
task/deterministic-agent file byte-for-byte against P0.2 da2ff0b before running.

Model telemetry is instrumented inside adapters: model_call_count, input/output_tokens,
model_latency_ms, estimated_cost when supplied, and agent wall time. It is labelled
adapter_instrumentation, not trusted broker billing. Provider tool_time_ms, tool
counts and full worker wall are parent-measured by frozen infrastructure. Worker
crash/timeout means unavailable model usage, not zero. No built-in price table;
the supplied HTTP transport leaves cost null. Generic clients can report known cost.

The separate benchmark driver combines that telemetry with unchanged P0.2 checks,
score and renderer; the deterministic runner's counters are not patched or reused
as real model counts. Configured runs save per-side results/traces, checks, score,
manifest and summary. Exit 1 indicates any benchmark case failure; exit 2 means
missing/invalid model configuration; no configuration means NOT RUN, not PASS.
Declared family/configuration is recorded separately from provider/model verification.

Trusted internal code only; filesystem isolation remains absent. No hidden/hostile
independent evaluator security is claimed. No live Ads/SellerOS tools are added.
