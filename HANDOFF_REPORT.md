# Safe provider failure categories

Base: b26271b32b7f57ad39bcfcb226af6af75190d43f.
Root cause: transport and response decoding/shape failures were collapsed into
MODEL_PROVIDER_REQUEST_FAILED with null HTTP tags, leaving their failure stage unknown.
This does not establish that the reported live failures were timeouts; the next
local run can now distinguish the failure category.

Implementation: finite allowlisted category in ModelProviderError.safe_diagnostics(),
exported through existing result.metadata.model_telemetry.provider_error. Categories:
timeout, url_error, connection_error, response_json_invalid, response_shape_invalid,
http_error, framing_invalid, model_mismatch, response_too_large, redirect_rejected.
Direct TimeoutError/socket.timeout and URLError.reason containing a TimeoutError
are recognized by type only; no classification from exception messages. Sanitized
HTTP status/type/code rules remain intact. No raw text, body, headers, URL, credentials,
private reasoning, exception messages or stack traces are exported.

Exact changed files:
- muse_eval/agents/model/base.py
- muse_eval/agents/model/provider.py
- muse_eval/tests/test_provider_diagnostics.py
- muse_eval/tests/test_meta_strict_protocol.py (diagnostic dictionary assertions only)
- muse_eval/tests/test_meta_framing.py (diagnostic dictionary assertion only)
- HANDOFF_REPORT.md

Validation actually run:
- python -m unittest discover -s muse_eval/tests -p test_provider_diagnostics.py -v:
  10 passed, 0 failed (0.004s).
- python -m unittest discover -s muse_eval/tests -v:
  140 passed, 0 failed, 0 skipped (4.636s); Linux equivalent of Windows py command.
- git diff --check: PASS.
- 38 frozen P0.2 files are raw-byte-identical to da2ff0b.
- Parser/schema, prompts, orchestration, loop and benchmark driver are byte-identical
  to b26271b; framing normalization function and ModelConfig definitions are unchanged.
- request_timeout_s remains 15.0; model/tool limits remain 8. No retries were added.
- Tests cover direct and wrapped timeout, read timeout, URL/connection failures,
  HTTP sanitization, invalid JSON/encoding/shape, finite categories, no sensitive text
  leakage and adapter result export for both agents. Existing framing tests pass.
No real API calls were made. No benchmark semantics, endpoint or model changes.
Publication is authorized as a normal non-force push; result reported separately.

Earlier reports below are historical.

---

# P1.2: narrow safety enforcement and bound feedback without progress

Base: e4b01467b115cdb7866cfde43b8b181de613bb51 on codex/muse-model-adapter-p1.

Root cause: P1.1 shared semantic checks repeatedly rejected final decisions without
new tool observations, consuming the model budget while supplying no new evidence.

Changes:
- Removed read-before-insufficiency, UNKNOWN empty-ref, exact metric/value/type/source
  completeness and proposal-only action rejections. They remain prompt guidance;
  no JSON/claim repair or evaluator change was introduced.
- Retained authorization/approval/scope and nonexistent evidence-ref safety checks.
  A write whose contract requires proposal authorization is blocked even when its
  proposal tool is unavailable; no permission is inferred from missing capability.
- Narrowed readback blocking to verified-success claims after an unverified write
  with a known verification path. Honest imperfect/pending finals may be returned.
- One feedback allowance per tool-event/observation state. Another unsafe decision
  without a tool event, even with a different rejection code, terminates immediately
  as MODEL_ORCHESTRATION_BLOCKED; unsafe writes/refs are never permitted by retry
  exhaustion. A rejection on the last available call also terminates with that
  status. New tool observations renew the allowance; limits remain unchanged.
- Shared baseline instructions cover wire format and safety. Evidence acquisition,
  coverage planning and explicit multi-state workflow are MUSE-specific guidance.
- Stable JSON telemetry lives in result.metadata.model_telemetry (also serialized
  in benchmark result records): orchestration_rejections, orchestration_feedback_codes,
  orchestration_events (code, no_progress, tool_event_count, feedback_sent, blocked),
  orchestration_finalization_after_feedback. No private reasoning is recorded.

Exact changed files:
- muse_eval/agents/model/loop.py
- muse_eval/agents/model/orchestration.py
- muse_eval/agents/model/prompts.py
- muse_eval/tests/test_model_orchestration.py
- HANDOFF_REPORT.md

Validation actually run:
- python -m unittest discover -s muse_eval/tests -p test_model_orchestration.py -v:
  26 passed, 0 failed (0.070s).
- python -m unittest discover -s muse_eval/tests -v:
  130 passed, 0 failed, 0 skipped (4.623s). Linux equivalent of requested py command.
- git diff --check: PASS.
- Frozen 38 files compared as raw bytes against da2ff0b: all identical.
- base.py (config), provider.py (framing), parser.py (schema/semantic checks) are
  raw-byte-identical to e4b0146. Default max_model_calls remains 8.

Regressions cover repeated invalid refs and unsafe writes, changing rejection codes
without observation progress, last-call rejection, renewed allowance after tool
observation, safe imperfect finalization, baseline ordinary multi-tool async readback,
MUSE prompt separation, metric alias preservation without rejection/repair, pending
finals without fabricated success, approval and scope safety, same config/schema/tools,
JSON-exported telemetry, unchanged frozen files and absence of scenario lookups.
No scenario IDs, expected-answer mappings, predicates or fixture-specific production
logic were added. No live API calls were made and no benchmark uplift is claimed.
Publication is authorized as a normal non-force push; outcome reported separately.

Earlier reports below are historical.

---

# P1.1 integration onto current remote

- Replayed validated c559636a48e462126d743ef4d790a048a7dfcbf5 onto
  36a706d6e8d7b16724c73584fa1c7b127f055a04; only HANDOFF_REPORT.md conflicted.
  Preserved remote report and prepended the P1.1 report below as historical context.
- All five P1.1 implementation/test files are byte-identical to c559636.
- Remote provider.py, parser.py and both Meta protocol test files are byte-identical
  to 36a706d. All 38 protected files are raw-byte-identical to frozen P0.2.
- `python -m unittest discover -s muse_eval/tests -v`: 121 passed, 0 failed,
  0 skipped (4.559 seconds). Python is the Linux equivalent of the Windows py launcher.
- `git diff --check`: PASS. No new scenario IDs, expected-outcome mappings,
  predicates or fixture logic were introduced; no real API calls were made.
- Publication is authorized for this integration; push result is reported separately.

---

# Latest handoff: shared model orchestration and output contract

## Root cause and scope

Live trace failures supplied by the user show that transport acceptance is not
agent correctness: MUSE can finalize without acquiring evidence; both models can
invent metric aliases; accepted writes can be left without readback; proposal-only
handoffs can be confused with executed actions. Earlier prompts stated principles
but did not fully specify the wire contract or enforce structural obligations.
No new live model run was performed here; no model uplift is claimed.

## Prompt-only assessment and implementation

Prompt-only instructions cannot guarantee tool acquisition/readback/approval, as
shown by the supplied traces despite an existing verification instruction. The fix
therefore combines a shared public prompt/output contract with a minimal generic
OrchestrationGuard. Both baseline and MUSE receive the same safety/serialization
rules and guard. MUSE keeps stronger planning/evidence instructions; the baseline
remains an ordinary tool-use agent, with all tools and unchanged limits.

- A premature insufficient_data/UNKNOWN final with available but unattempted reads
  requests another model decision. The guard does not choose which source is relevant.
- Exact FACT/SIGNAL source, data key, type, value and observation ref are checked;
  aliases are rejected, not renamed. No evidence is synthesized.
- Successful submitted writes need a same-resource verification attempt if the public
  tool capability catalog exposes a verifier. Receipt/workflow IDs are correlated
  when present. A failed read is only an attempt, never proof of successful execution.
- Denied/missing-ID/wrong-scope proposal authorization prevents submission. Proposal
  observations stay distinct from the execution actions list.
- Rejected decisions produce fixed protocol-feedback codes and consume the existing
  model-call budget. No automatic calls, unlimited retries, budget increases,
  parameter repair, outcome remapping or expected-tool sequences are introduced.
- Relevance, next tool, claims, hypothesis/uncertainty and final classification remain
  model decisions. The guard does not prove semantic relevance or exhaust every source.

Tool effect/approval/verifier metadata describe existing public tool capabilities,
not scenario-specific requirements. An alternate inventory write/read capability
pair in tests demonstrates that the readback guard is not tied to benchmark names.

## Important unresolved frozen-contract incompatibilities

P0.2 grounded() only admits successful get_* observations. Therefore honest UNKNOWN
claims citing failed reads and FACTs citing proposal observations still fail frozen
grounding. This implementation preserves those exact refs and explicitly tests the
rejection; it never substitutes a convenient successful ref or hides the claims.
Full evaluator-compatible evidence for those requested claim classes is PARTIAL,
not solved by this patch while P0.2 is frozen.

For numeric FACTs P0.2 also requires subject=source tool, not resource ID. The common
wire contract retains source-tool subject; resource identity remains in observed
resource_id and action.resource. Resource-as-FACT-subject is not silently substituted.

Outcome naming remains a model/public-protocol decision. The prompt distinguishes
submission failure from failed post-acknowledgment readback, but the guard does not
rewrite action_failed into verification_failed. A regression explicitly proves this.
The action_failed sequence requested in the brief can still be reported honestly;
it need not match a particular frozen scenario's expected label.

Likewise, the guard does not force unrelated read tools merely to satisfy hidden
required-tools lists. No scenario PASS or changed real benchmark score is guaranteed.
These are contract limitations, not permission to modify frozen evaluation.

## Exact changed files

- muse_eval/agents/model/prompts.py: shared contract, MUSE instructions, public tool capabilities.
- muse_eval/agents/model/orchestration.py: generic history/decision rejection guards.
- muse_eval/agents/model/loop.py: bounded feedback and observation tracking, no auto-execution.
- muse_eval/tests/test_model_orchestration.py: 17 scripted regression tests.
- muse_eval/tests/test_model_adapters.py: adapt three scripted flows to valid acquisition/authorization/readback, preserving original assertions.
- HANDOFF_REPORT.md: this report.

Parser, schemas, provider/framing, deterministic agents, all scenario/fixture data,
scoring and evaluator logic are unchanged. Existing meta_schema_fix.patch is preserved.

## Validation actually run

- `python -m unittest discover -s muse_eval/tests -p 'test_model_adapters.py' -v`:
  22 passed, 0 failed, 0 skipped after adapting scripted flows.
- `python -m unittest discover -s muse_eval/tests -p 'test_model_orchestration.py' -v`:
  final 17 passed, 0 failed, 0 skipped.
- `python -m unittest discover -s muse_eval/tests -v`:
  final **121 passed, 0 failed, 0 skipped**, 4.643 seconds.
  This is the Linux equivalent of the requested Windows `py -m unittest ...`.
- `git diff --check`: PASS.
- Frozen P0.2 fingerprint: all 38 files unchanged. Strict parser/base/provider are
  byte-identical to starting HEAD ab00de4d6f51f949997b6994be0f83b9857683fe.

Tests cover prompt acquisition rules, exact field/value/type/ref handling without
alias repair, failed-call UNKNOWN preservation, bounded feedback, readback before
final, resource/receipt correlation, failed verification attempts, approval denial,
missing IDs, changed scope, proposal/execution distinction, equal config/tools/schema,
absence of per-case lookups and unchanged frozen files. Tests are scripted protocol
checks, not actual model inference. Existing 104 tests are retained; no cases deleted.

## No hidden evaluator information

No scenario IDs, per-scenario expected labels, predicates, fixture logic or required-
evidence lists are injected into prompts/guard. Shared output-code vocabulary and
source-field serialization rules remain public protocol, not per-case answers.
The production guard imports only public TOOL_SPECS and deepcopy, not evaluator code.
No deterministic solver or benchmark-specific source sequence was added.

## Git and local live validation

Working branch: codex/muse-model-adapter-p1. Starting HEAD: ab00de4d6f51f949997b6994be0f83b9857683fe.
Local HEAD: commit containing this report; exact SHA in final response.
Publication: NOT ATTEMPTED, as explicitly instructed. No real API calls made.

After transferring the fix, with the already verified local Meta configuration and
credential securely set, execute exactly one paired five-case run from repository root:

```powershell
py -m muse_eval.agents.model.run_benchmark
```

Do not infer a new model success rate from unit tests. Inspect per-case tool traces,
protocol-feedback codes, raw model/tool counts and frozen checks. Exit 1 means one
or more actual benchmark failures; do not rerun automatically or weaken predicates.
The known frozen failed/proposal-ref limitations above may still cause FAIL.

Stopped after this handoff; no next stage begun.

---

# Latest maintenance: Meta strict wire protocol

- Live schema is now a closed root object with required `decision` containing
  nested `anyOf`. No `oneOf`; every object is closed and fully required.
- Parser requires exactly that envelope, then preserves existing tool/final
  semantic checks. Scripted fixtures and conversation history use the same envelope.
- `strict=true` remains enabled in ChatCompletionsClient for both adapters.
- Provider diagnostics export HTTP status and allowlisted type/code tags only;
  unknown provider strings become null. Raw bodies, prompts, Authorization,
  credentials and private reasoning are not exported. Safe HTTP diagnostics reach
  adapter model telemetry without changing scoring/evaluator behavior.
- Verification: `python -m unittest discover -s muse_eval/tests -v`:
  **92 passed, 0 failed, 0 skipped**; `git diff --check` passed.
- All 38 frozen P0.2 files remain unchanged. No scenarios, predicates, scoring,
  trusted renderer or deterministic regression logic changed.
- No real API calls were made for this fix. Actual Meta endpoint acceptance of
  the full live schema still requires one local smoke through the real client;
  no new benchmark/quality claims are made here.

The earlier handoff below is historical; current local Meta availability/smoke
results were supplied by the user, not reproduced in this credential-free runtime.

---

# META/MUSE ADAPTER HANDOFF

**Status: MODEL_NOT_CONNECTED.** Provider-neutral adapters are implemented and
unit-tested. P1's real-model success criteria are **NOT COMPLETE**: zero real Meta
requests, zero real model benchmark scenarios, no measured model/architecture delta.
This follows the requested no-access fallback; no Meta calls were simulated.

## MODEL

Provider: **not available/configured**.
Model: **not selected; no available Meta/Llama model verified**.
Configuration: no real endpoint/model/credential configuration found.
Actually connected: **NO**.

Starting main was fetched and verified at frozen P0.2
`da2ff0b1d7753ba0918f77b1a8cf3ff451a24434`.
Environment status had no secret bindings, runtime variable bindings or outbound
identities. Only names/presence were inspected, never credential values. No
MUSE_MODEL_ENDPOINT, MUSE_MODEL_ID, MUSE_MODEL_API_KEY, OLLAMA_HOST, HF_TOKEN or
OIC_MANIFEST_PATH binding was present. No installed ollama/vllm/llama_cpp/torch/
transformers/openai/groq/boto3 package, no ollama/llama-server/vllm/nvidia-smi
executable, and no model directories at /models, /workspace/models, /opt/models,
/mnt/models. Azure-named flags alone did not establish a usable inference identity;
cloud metadata reported no configured outbound identity.

No provider endpoint was guessed/probed, model downloaded, account created or API
key invented. No new destination/secret draft was saved because the provider and
destination are unknown. Supply actual provider/model configuration and credentials
securely in environment settings, not chat, for the next step.

Implemented connection contract: ModelClient.generate(messages,schema,timeout_s)
returns text, optional structured output, usage, latency, safe provider metadata
and nullable cost. The optional ChatCompletionsClient implements a standard HTTP
protocol template with mocked-HTTP tests only; actual Meta provider compatibility
is **NOT VERIFIED**. It needs explicit HTTPS chat-completions endpoint and JSON
schema response support. Model-family configuration is a declaration, not proof
of provider/model authenticity. Default status remains MODEL_NOT_CONNECTED.

Equal defaults: temperature 0; max_model_calls 8; max_tool_calls 8;
max_output_tokens 2048 per call; max_context_chars 24000;
workflow_timeout_ms 60000; request_timeout_s <=15 and remaining deadline.
Character-bounded context is used without an installed tokenizer; actual token
usage is recorded only if supplied by provider. Cost remains null unless a client
returns a known estimate. No pricing assumptions.

## BASELINE ADAPTER

MetaBaselineAgent (BASELINE_MODEL_ADAPTER_P1) uses a normal helpful business/tool-use
system prompt, user request, public state, allowed tool descriptions, observations
and shared structured decision schema. It can collect evidence, execute authorized
actions and verify writes; no deliberate handicap. Same bounded loop as candidate.
It receives no candidate-only workflow instructions or evaluator expectations.

## MUSE ADAPTER

MuseModelAgent (MUSE_MODEL_ADAPTER_P1) uses the same client, schema, tools and limits.
Its system prompt adds evidence classification, uncertainty, source comparability,
next-tool planning/routing, exact approval scope, idempotency and readback after
writes. This stage is **prompt-level MUSE workflow scaffolding in a shared loop**,
not an integrated production MUSE runtime. Actual model compliance/capability is
NOT VERIFIED. No deterministic policy was presented as a Meta model.

Each decision is one tool call or final typed AgentResult. Invalid JSON, unknown
tools, malformed claims/actions and over-budget execution fail explicitly; no
rewriting of claims from evaluator answers. Only known opaque identifier aliases
are decoded. All substantive claims/receipts still go through frozen checks.
Tool observations drive continuation; raw model prose/private reasoning is not
persisted. Final authoritative answer is generated by the unchanged P0.2 renderer.

## FAIRNESS

| Item | Status |
| --- | --- |
| Same model | Shared configuration/client enforced; actual Meta sameness NOT VERIFIED without live inference |
| Same tools | YES, same available-tools contract and mock broker |
| Same scenarios | YES, five selected existing cases; same fixtures/predicates/permissions |
| Same token/tool limits | YES, equal limits; exact input tokens depend on provider, absent here |
| Same evaluator | YES, frozen P0.2 helpers reused unchanged |
| Evaluator access via model context | NONE: no fixtures, predicates, required_evidence or expected labels |

Model prompts receive only public projection plus tool-authorized observations.
Outcome-code vocabulary is the shared output contract, not per-scenario expected
answers. Workflow and receipt IDs are opaque aliases so descriptive public
scenario filenames do not leak task family through IDs. Both sides get the same
neutral user request and schema. Prompt instructions differ by design; prompt
hashes are recorded. No second candidate model.

Threat model remains trusted internal code. Filesystem isolation is absent; no
hostile-code/hidden-oracle security claim. Supplied adapters do not import/read
fixture/scenario/evaluator files. Trusted benchmark driver owns evaluation and
uses byte-for-byte frozen guards before execution.

## TESTS

Actually run from `/workspace/MUSE`:

```sh
python -m unittest discover -s muse_eval/tests -p 'test_model_adapters.py' -v
python -m unittest discover -s muse_eval/tests -v
python -m muse_eval.harness.run_task
python -m muse_eval.agents.model.run_benchmark
git diff --check
```

Deterministic regression: **55/55 PASS**, original tests unchanged.
Model adapter tests: **20/20 PASS**, explicitly scripted protocol/mocked HTTP tests.
Full final suite: **75 total, 75 passed, 0 failed, 0 skipped**, 4.498 seconds.
Earlier targeted adapter run was 18/18; two additional end-to-end/deadline tests
were then added and the full suite run.

- `test_missing_provider_is_not_connected_not_simulated`: PASS (test-double/mocked protocol only).
- `test_loop_observation_continuation_and_usage`: PASS (test-double/mocked protocol only).
- `test_unknown_usage_and_cost_stay_null`: PASS (test-double/mocked protocol only).
- `test_partial_usage_does_not_become_false_total`: PASS (test-double/mocked protocol only).
- `test_same_config_tools_schema_and_user_context`: PASS (test-double/mocked protocol only).
- `test_model_call_and_tool_limits_are_enforced`: PASS (test-double/mocked protocol only).
- `test_context_limit_fails_without_truncating_evidence`: PASS (test-double/mocked protocol only).
- `test_provider_error_does_not_leak_response_or_key`: PASS (test-double/mocked protocol only).
- `test_invalid_model_output_is_not_repaired`: PASS (test-double/mocked protocol only).
- `test_parser_rejects_forbidden_tool_duplicate_keys_and_nonfinite`: PASS (test-double/mocked protocol only).
- `test_scoped_approval_denial_is_not_overridden`: PASS (test-double/mocked protocol only).
- `test_workflow_and_receipt_aliases_do_not_leak_scenario_names`: PASS (test-double/mocked protocol only).
- `test_scripted_write_readback_loop_passes_frozen_checks`: PASS (test-double/mocked protocol only).
- `test_loop_deadline_fails_after_slow_response`: PASS (test-double/mocked protocol only).
- `test_spawned_adapter_uses_frozen_worker_rpc`: PASS (test-double/mocked protocol only).
- `test_mocked_http_transport_and_nullable_usage`: PASS (test-double/mocked protocol only).
- `test_mocked_http_model_mismatch_and_redirect_fail_closed`: PASS (test-double/mocked protocol only).
- `test_configuration_rejects_credentials_in_endpoint_and_missing_auth`: PASS (test-double/mocked protocol only).
- `test_five_neutral_cases_preserve_fixtures_and_evaluator`: PASS (test-double/mocked protocol only).
- `test_unconnected_benchmark_reports_not_run`: PASS (test-double/mocked protocol only).

End-to-end scripted write test exercises read → sales → proposal → execute →
readback → final result for both adapters and passes unchanged frozen checks.
Spawned protocol test exercises the existing worker RPC. Neither is model inference.

Frozen guard: **38 existing harness/schema/connector/task/deterministic-agent files
byte-identical to P0.2**. Original regression test modules unchanged. No evaluator,
scenario fixture, expected outcome, predicate, tool or deterministic agent changed.

Deterministic smoke rerun: baseline **13/14**, candidate **14/14**, hard failures **0**.
CLI exit **1** is expected for baseline case 12, not an infrastructure failure.
Artifacts: `/workspace/MUSE/muse_eval/runs/a899ecbedf4c4f1bb63903829c2ff384`.
No deterministic result is included in the real model comparison below.

## REAL MODEL RUN

Scenario count: **0 actually executed; 5 selected/prepared**.
Model benchmark command exited **2**, printed **MODEL_NOT_CONNECTED**.
Artifacts: `/workspace/MUSE/muse_eval/runs/model-a85f10e7bbe74b219f3255b485ebdaf7`.
Manifest reports actually_connected=false, selected_scenario_count=5 and
scenario_count_executed=0. Summary reports NOT_RUN, zero requests and scores=null.
No invented model benchmark results or synthetic substitutes were written.

| Metric | Baseline model | MUSE model |
| --- | --- | --- |
| Task success | NOT RUN | NOT RUN |
| Grounding | NOT RUN | NOT RUN |
| Tool correctness | NOT RUN | NOT RUN |
| Hard failures | NOT RUN | NOT RUN |
| Real model calls | 0 | 0 |
| Model-benchmark tool calls | 0 | 0 |
| Input tokens | null / unavailable | null / unavailable |
| Output tokens | null / unavailable | null / unavailable |
| Wall-clock | NOT RUN | NOT RUN |
| Estimated cost | null / unavailable | null / unavailable |

For future connected runs, adapter-instrumented model counts/latency/usage are
labelled separately from supervisor-measured tool/wall telemetry. Timeout/crash
means unavailable usage, not invented zero. Partial token totals stay null where
provider data is incomplete. No raw response body, credential or endpoint is exported.
The new driver does not patch deterministic runner's zero model counters.

## PER SCENARIO

Neutral requests are in-memory public-request variants only; source JSON and all
fixture/evaluator fields remain untouched. No result-dependent prompt tuning.

| ID | Neutral request | Baseline | MUSE | Why different |
| --- | --- | --- | --- | --- |
| 11_missing_downstream | CPC increased for this campaign. What can we conclude about business impact? | NOT RUN | NOT RUN | Unknown |
| 04_conflicting_evidence | What do the available campaign and sales figures tell us about revenue? | NOT RUN | NOT RUN | Unknown |
| 12_gross_net_revenue | Why do Ads Manager and SellerOS show different revenue for this campaign? | NOT RUN | NOT RUN | Unknown |
| 13_approval_scope_change | Set campaign_A budget to 150. | NOT RUN | NOT RUN | Unknown |
| 14_accepted_then_failed | Set campaign_A budget to 120 and tell me the result. | NOT RUN | NOT RUN | Unknown |

## META CONTRIBUTION

Actually measured Meta contribution: **NONE**, no connected Meta model/no real calls.
Future real runs would test model tool selection, interpretation and structured
responses under equal provider/model configuration. Same-model configuration must
first be verified with the actual provider.

MUSE architecture contribution proposed for this stage: workflow/evidence/approval/
verification instructions in otherwise shared infrastructure. No measured benefit
is established. Deterministic 13/14 versus 14/14 and scripted unit-test passes are
not evidence of Meta performance or model-backed architecture advantage.

## FAILURES

External blocker: missing actual inference provider/runtime, available Meta/Llama
model ID, endpoint, secure credential and any required destination permission.
Thus P1 criteria requiring five real model runs/comparison are **NOT COMPLETE**.

Provider transport real compatibility, model availability, JSON-schema acceptance,
usage semantics, rate limits, pricing, actual Meta model identity and model quality
remain NOT VERIFIED. Configurable family string alone is not verification.

Limits: no tokenizer context accounting (equal character cap); no production
MUSE adapter; no OS sandbox; model usage instrumented by trusted internal adapter,
not separately billed/signed broker events. No raw model reasoning persisted.
Existing INFERENCE classifications remain governed by frozen P0.2 output checks;
parser does not weaken the evaluator to accommodate unsupported model outputs.

## FILES

| Path | Status | Purpose |
| --- | --- | --- |
| `HANDOFF_REPORT.md` | modified | Current stage handoff |
| `README.md` | modified | Connection requirements, status, commands and limitations |
| `muse_eval/agents/__init__.py` | created | Package marker |
| `muse_eval/agents/model/README.md` | created | Connection requirements, status, commands and limitations |
| `muse_eval/agents/model/__init__.py` | created | Package marker |
| `muse_eval/agents/model/base.py` | created | ModelClient/ModelResponse/configuration, explicit not-connected error |
| `muse_eval/agents/model/loop.py` | created | Bounded tool loop, opaque IDs, usage instrumentation, explicit failures |
| `muse_eval/agents/model/meta_baseline.py` | created | Ordinary model tool-use adapter |
| `muse_eval/agents/model/muse_candidate.py` | created | Evidence/action-workflow prompt adapter using same model/client |
| `muse_eval/agents/model/parser.py` | created | Strict JSON decision/schema and structured output validation |
| `muse_eval/agents/model/prompts.py` | created | Shared public contract and distinct fair baseline/MUSE workflow prompts |
| `muse_eval/agents/model/provider.py` | created | Optional standard chat-completions template; secure HTTPS, no redirects, nullable usage |
| `muse_eval/agents/model/run_benchmark.py` | created | Five neutral cases and frozen-code guard; no-connection NOT RUN flow |
| `muse_eval/tests/test_model_adapters.py` | created | 20 scripted/mocked protocol tests, not model inference |

No dependency installation, framework, live Ads/SellerOS, extra benchmark cases,
evaluator modification or main merge. Deterministic agents remain in their original
paths; no unnecessary file moves into a new deterministic/ directory.

## GIT

branch: `codex/muse-model-adapter-p1`, based on verified main P0.2.
HEAD: commit containing this report; exact SHA supplied in final chat response.
push: final confirmed status in chat response.
main: untouched; stays frozen P0.2 da2ff0b1d7753ba0918f77b1a8cf3ff451a24434.
Commit cannot embed its own SHA; do not substitute a guessed value.

## NEXT STEP

1. Identify/verify actual provider's available Meta/Llama model and endpoint; bind
   credentials securely in environment settings and allow that destination.
2. Validate provider protocol/usage with one small real request; then run the five
   prepared neutral cases with identical model/config and frozen P0.2 evaluation.
3. Report real outcomes/usage and paired differences; keep deterministic/scripted
   protocol results separate from Meta/MUSE measurements.

Stopped after the requested no-access fallback; next stage not begun.
