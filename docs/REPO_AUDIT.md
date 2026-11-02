# MUSE — repository audit
Дата: 2026-11-02. Статус: research/design; harness не реализован.

## 1. Executive conclusion
Переносим экспериментальный протокол Soup: фиксированный task, честная пара baseline/candidate, единый runner, независимый evaluator, полный wall-clock, проверяемые артефакты, correctness до scoring. GPU-код не переносим. MUSE требует дополнительного независимого state/tool broker: текст агента и его собственный trace не являются доказательством действия.

## 2. Область и доказательства
Исходники прочитаны через GitHub; зависимости не устанавливались, benchmarks и тесты не запускались. Других конкретных URL репозиториев SellerOS/SignalBridge/MUSE в доступном контексте нет: их реализация НЕ аудирована. Название продукта не даёт основания предполагать существующие modules/API.

| Repository | Проверенная revision | Структура |
|---|---|---|
| [Starter](https://github.com/MakazhanAlpamys/soup-kernel-challenge) | c7c2fcd15972ce8b898d8d3ff732ee192c817ceb | harness/, task/, solution/ (example SwiGLU), tests/, templates/, LICENSE, NOTICE |
| [Final](https://github.com/BAITC-Hacks/hack-defd975c-byte) | HEAD e5ece7d86f86446739b0d6b36eac33b3614dce63 | тот же harness/task/tests + расширенный solution/, SUBMISSION.md |
| Measured solution | 1d888dc4f2d3d298dca6cddf26294783cd7f2187 | commit существует; message: Remove BOM so solution passes static AST rule check |

У обоих HEAD и measured commit каталог harness имеет tree SHA 6c8e1b84d0965673aeca8b39c312adfdc78fb562: байтово идентичное дерево evaluator. Measured solution tree: 34dc7eaea5ee4f96541961341f48563a270eff5f. HEAD не следует автоматически считать measured revision.

[SUBMISSION.md](https://github.com/BAITC-Hacks/hack-defd975c-byte/blob/e5ece7d86f86446739b0d6b36eac33b3614dce63/SUBMISSION.md) сообщает 78.6→46.9 s, 14345→6379 MiB, 1.677×, 2.249×, eval +0.008%, kernels 6.2%, 10/10 и 79 tests. Это repository-reported results, не независимое воспроизведение. 18/18 solution tests предоставлены пользователем; нельзя выдавать их за выполненные здесь. Для строгой provenance нужны оригинальные result.json/checks.json/logs и их hashes.

## 3. Exact files and patterns
Все пути ниже относительно Soup; source link: https://github.com/BAITC-Hacks/hack-defd975c-byte/tree/1d888dc4f2d3d298dca6cddf26294783cd7f2187

| File / symbol | Что действительно делает | Решение для MUSE |
|---|---|---|
| harness/run_task.py: train, make_config | same task, side flag, per-run dirs/cache/db | переписать orchestration вокруг agent worker, retain identical contexts |
| run_task.py: main | alternating AB/BA, package snapshots, separate profile | retain paired ordering; evaluate EVERY repeat |
| run_task.py: summarize | median wall, max memory; ratios | переписать: quality distribution, failure rate, p50/p95; no dropped failures |
| harness/common.py: run_logged, kill_group | parent perf_counter, timeout, process-group cleanup | pattern; remove GpuPoller, ENV inheritance and raw logs |
| common.py: file_sha256 | byte digest | маленький reusable helper после attribution; strict error handling |
| check_rules.py: solution_sha256 | deterministic path+bytes hash | rewrite canonical manifest, exclude generated files explicitly |
| check_rules.py: finite, compare_outputs | rejects missing/nonfinite data, invariant checks | pattern; typed schema + monetary/state assertions |
| check_rules.py: main | checks bound to result_sha256 and solution hash | retain binding, add evaluator/scenario/fixture/trace hashes |
| check_rules.py: run_tests | subprocess + exact 79 passed parsed from stdout | НЕ копировать count/parser; use JUnit test inventory, missing/skipped required tests fail |
| harness/score.py: admitted | all checks + same result digest required | retain admission-before-score, rewrite formula |
| harness/eval_adapter.py: evaluate | separate process, plain transformers+PEFT, no solution import | key independence pattern; MUSE evaluator consumes broker receipts/state |
| harness/_train.py: main / Probe | instrumentation installed before solution.apply | trusted telemetry/broker before candidate; no monkeypatch-based security |
| solution/__init__.py: apply | one patch registration entrypoint | adapt to apply(public_task_context) returning AgentResult |
| tests/conftest.py | per-test DB; removes ambient auth token; apply before regressions | fresh state, restricted environment, shared tests both implementations |
| solution/test_fused_loss.py | reference comparison, tie boundaries, ignored labels, refusal paths | metamorphic financial/approval/connector boundary tests |
| packed_qwen.py: _eligible; segmented_attention.py | guarded specialized path, state/shape invariants | explicit capabilities and fail-closed state transitions |
| task/task.yaml; prepare_data.py | fixed settings and public/hidden data concept | versioned scenario manifest; split agent-visible/evaluator-only data |

## 4. Dependencies and compatibility
Soup runtime: soup-cli==0.77.0, torch, Triton, transformers, PEFT, TRL, bitsandbytes, accelerate, datasets, PyYAML, pytest; README pins additional versions. MUSE не наследует этот environment. Proposed core: Python 3.11+, stdlib SQLite/Decimal/json, jsonschema (runtime), pytest (dev). YAML optional; JSON canonical validation. Model SDK only within model adapter.

Final solution adds bnb_cache.py, bnb_forward_cache.py, fp16_base.py, fused_loss.py, lora_nf4.py, norm.py, packed_qwen.py, segmented_attention.py, startup_warmup.py, swiglu.py and kernel tests. This is a specialized Qwen/T4 patch stack, not an agent evaluation engine. No CUDA/Triton/QLoRA dependency in MUSE harness.

## 5. Limits discovered in Soup
- Independent process is experimental separation, not a security sandbox: same filesystem/OS credentials can expose evaluator data.
- run_task evaluates first successful adapter of each side, not every repeat; MUSE must not inherit this blind spot.
- common.run_logged writes raw stdout and inherits os.environ: unacceptable for credentials/PII in agent traces.
- warm_up downloads model outside timed command. Precisely describe measurement boundary; do not claim all deployment provisioning was timed.
- profile is separate from scored measurement; own-kernel share excludes first two training steps while full wall-clock includes startup/JIT. These are different denominators.
- hash binding detects artifact mismatch, not authenticity when candidate can rewrite both files. Trusted evaluator and protected output store required.
- source AST scans/import bans do not prove absence of malicious behavior.
- regression count is brittle; sparse suite does not prove all numerical paths safe.

## 6. License / attribution
| Component | Verified source | Obligation / decision |
|---|---|---|
| Both Soup kits | LICENSE + NOTICE, Apache-2.0 | retain license, relevant NOTICE/copyright, mark changed copied files; preserve third-party notices |
| Soup copied regression tests | NOTICE: five tests from Soup v0.77.0 Apache-2.0 | do not copy irrelevant tests; source attribution if adapted |
| Training dataset | NOTICE: HF MIT card, upstream Stanford Alpaca CC BY-NC 4.0 | conflicting upstream provenance requires review; do NOT reuse data in MUSE |
| Qwen weights | NOTICE says Apache-2.0 | no weight transfer needed |
| Final measured performance | SUBMISSION.md and user report | attribute team work, commit and measurement conditions |

Architecture inspiration alone is not a source-code copy. Still keep provenance notes; copied code requires its notices. Meta model weights require separate model-specific terms review; an SDK license does not license weights.

## 7. Additional repositories: researched shortlist
Scope is deliberately small. No framework installation. Exact sources inspected for tau-bench, Inspect and VCR.py; other candidates explicitly provisional.

| Repository / license | Relevant file | Useful / fit | Reuse / dependency / lock-in | Do NOT copy / attribution | Priority |
|---|---|---|---|---|---|
| [sierra-research/tau-bench](https://github.com/sierra-research/tau-bench), MIT, SHA 59a200c6d575d595120f1cb70fea53cef0632f6b | tau_bench/envs/base.py: reset, step, calculate_reward | resettable business state, action-based reward, repeated reliability | architecture only; full package medium weight; low vendor lock-in | evaluator mutates self.data to replay expected actions; use separate oracle state instead. Whole-state hash may reject valid alternatives; substring outputs do not prove grounding. MIT notice if copied | HIGH |
| [UKGovernmentBEIS/inspect_ai](https://github.com/UKGovernmentBEIS/inspect_ai), MIT, SHA 1f1a0039d49c628a41898a7a7ba4843c5bbbc91b | src/inspect_ai/approval/_approval.py; docs/approval.qmd | typed approve/modify/reject/terminate/escalate; design reference for human control | architecture only initially; large dependency compared with explicit runner; moderate framework coupling | typed approval object alone is not enforcement; do not add whole framework for enum. Preserve MIT notice if copied | HIGH |
| [kevin1024/vcrpy](https://github.com/kevin1024/vcrpy), MIT, SHA 7aaaefe14721cdbe8e690350290aa73b3bb4a03e | vcr/cassette.py; vcr/filters.py; LICENSE.txt | HTTP record/replay, request/response sanitization | optional test-only dependency after semantic replay proves insufficient; small/medium weight; low lock-in | HTTP cassette is not a stateful financial oracle; no raw credentials, unknown replay cannot fall through to live. Preserve MIT notice if copied | MEDIUM |
| [apple-aiml-research/ToolSandbox](https://github.com/apple-aiml-research/ToolSandbox) | tool_sandbox/common/evaluation.py candidate path — NOT verified in this audit | stateful milestones/insufficient-information design supported by Apple research paper | architecture study only; pyproject has many pinned dependencies; no install | license and file path NEED SOURCE VERIFICATION; do not reuse code/data until checked; do not inherit device-domain scenarios | MEDIUM |
| [meta-llama/llama-stack](https://github.com/meta-llama/llama-stack) | current agent/inference API file paths UNKNOWN | possible Meta model/tool adapter reference | provisional only; canonical location/version/license not resolved through connector; likely substantial service dependency, must measure | no forced framework dependency to claim Meta relevance; check official current source and model terms before adoption | LOW |

ToolSandbox primary explanation: https://machinelearning.apple.com/research/toolsandbox-stateful-conversational-llm-benchmark ; project dependency source: https://github.com/apple-aiml-research/ToolSandbox/blob/main/pyproject.toml . It supports milestone/state dependency ideas, not permission to copy its dataset. VCR docs: https://vcrpy.readthedocs.io/en/latest/advanced.html .

## 8. META rules verification
No exact official META rules document was resolved from available Library search. Soup README is challenge-specific, not an official source for MUSE/META submission. Project description/public GitHub/video <=3 min/Meta importance/ecosystem experience/partner experience/optional social link are USER-PROVIDED REQUIREMENTS — NEEDS SOURCE VERIFICATION. Do not silently promote these to official wording.

Potential apparent discrepancy: Soup SUBMISSION lists a registered team, while MUSE context says solo participant. These refer to different submission contexts; do not combine identities or infer a rule violation. Official MUSE registration status still requires its own source.
