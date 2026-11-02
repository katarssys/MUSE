import argparse
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
from time import perf_counter
from uuid import uuid4
from ..schemas.scenario import Scenario
from ..schemas.result import AgentResult, TaskContext
from ..schemas.trace import Trace, timestamp, sanitize
from ..connectors.mock import MockConnector
from ..baseline.agent import BaselineAgent
from ..candidate.agent import CandidateAgent
from .telemetry import Telemetry
from .check_rules import check_rules
from .score import score
from .worker import execute_agent
from .idempotency import InMemoryActionLedger
from .render import apply_trusted_presentation
import subprocess

PACKAGE = Path(__file__).resolve().parents[1]

def run(scenario_dir=None, output_root=None, agents=None, timeout_ms=3000):
    started = perf_counter()
    paths = sorted(Path(scenario_dir or PACKAGE / "task/scenarios").glob("*.json"))
    scenarios = [Scenario.load(p) for p in paths]
    if not scenarios or len({s.id for s in scenarios}) != len(scenarios):
        raise ValueError("Scenarios must be nonempty with unique IDs")
    run_id = uuid4().hex
    output = Path(output_root or PACKAGE / "runs") / run_id
    output.mkdir(parents=True)
    results, traces, checks, scores = {}, {}, {}, {}
    for name, agent in (agents or {"baseline": BaselineAgent(), "candidate": CandidateAgent()}).items():
        results[name], traces[name], checks[name], scores[name] = [], [], [], []
        for scenario in scenarios:
            telemetry = Telemetry()
            ledger = InMemoryActionLedger()
            events = []
            completed = True
            worker_spans = []
            for episode in range(scenario.success_conditions.get("workflow_executions", 1)):
                connector = MockConnector(scenario, telemetry, ledger)
                connector.event_prefix = f"episode:{episode+1}:"
                result, episode_completed, span = execute_agent(agent, scenario, connector, timeout_ms)
                completed = completed and episode_completed
                worker_spans.append(span)
                events.extend(deepcopy(connector.events))
                if not episode_completed:
                    break
            result.tool_calls = deepcopy(events)
            # Include result serialization in active workflow span; grading is separate.
            json.dumps(asdict(result), allow_nan=False)
            stats = telemetry.snapshot()
            stats["worker_spans"] = worker_spans
            evaluation_started = perf_counter()
            report = check_rules(scenario, result, events, completed)
            result = apply_trusted_presentation(result, report)
            trace = Trace(scenario.id, agent.version, timestamp(), events, result.evidence,
                          result.decision_summary, result.approval_state, result.actions,
                          {"checks": report["checks"]}, result.outcome, stats["total_wall_clock_ms"],
                          stats["model_call_count"], stats["tool_call_count"], stats["estimated_cost"])
            stats["evaluation_wall_clock_ms"] = (perf_counter() - evaluation_started) * 1000
            results[name].append({"scenario_id": scenario.id, "result": asdict(result), "telemetry": stats})
            traces[name].append(trace.to_dict())
            checks[name].append({"scenario_id": scenario.id, **report})
            scores[name].append({"scenario_id": scenario.id, **score(report, stats, scenario.success_conditions)})
        for filename, data in [(name, results[name]), ("trace_" + name, traces[name])]:
            (output / (filename + ".json")).write_text(json.dumps(sanitize(data), indent=2))
    metadata = {"run_id": run_id, "timestamp": timestamp(), "python": platform.python_version(),
                "scenario_count": len(scenarios), "agents": {k: a.version for k, a in (agents or {"baseline": BaselineAgent(), "candidate": CandidateAgent()}).items()},
                "scenario_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                "total_wall_clock_ms": (perf_counter() - started) * 1000,
                "isolation_assurance": "LOCAL_TRUSTED_ONLY_PROCESS_RPC",
                "workflow_measurement_scope": "connector/worker initialization, apply, RPC, result transfer, shutdown, result serialization; grading and bulk artifact writes excluded",
                "source_sha256": {str(p.relative_to(PACKAGE)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(PACKAGE.rglob("*.py"))},
                "artifact_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob("*.json")},
                "measurement_scope": "scenario loading, both adapters, checks, scoring and all artifact writes; excludes final timing field update"}
    for filename, data in [("checks", checks), ("score", scores), ("metadata", metadata)]:
        (output / (filename + ".json")).write_text(json.dumps(sanitize(data), indent=2))
    metadata["artifact_sha256"].update({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob("*.json") if p.name != "metadata.json"})
    metadata["git_head"] = subprocess.check_output(["git", "-C", str(PACKAGE.parent), "rev-parse", "HEAD"], text=True).strip()
    metadata["git_dirty"] = bool(subprocess.check_output(["git", "-C", str(PACKAGE.parent), "status", "--porcelain"], text=True))
    metadata["total_wall_clock_ms"] = (perf_counter() - started) * 1000
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2))
    return output

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout-ms", type=int, default=3000)
    args = parser.parse_args()
    output = run(args.scenarios, args.output, timeout_ms=args.timeout_ms)
    print(output)
    scores = json.loads((output / "score.json").read_text())
    return int(any(s["status"] != "passed" for group in scores.values() for s in group))

if __name__ == "__main__":
    raise SystemExit(main())
