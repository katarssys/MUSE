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

PACKAGE = Path(__file__).resolve().parents[1]

def run(scenario_dir=None, output_root=None, agents=None):
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
            connector = MockConnector(scenario, telemetry)
            context = TaskContext(scenario.id, scenario.user_request, deepcopy(scenario.initial_state),
                                  list(scenario.available_tools), connector)
            completed = True
            try:
                result = agent.apply(context)
                if not isinstance(result, AgentResult):
                    raise TypeError("Adapter must return AgentResult")
            except Exception as exc:
                completed = False
                result = AgentResult("Adapter failed", outcome="error", metadata={"exception_type": type(exc).__name__})
            result.tool_calls = deepcopy(connector.events)
            stats = telemetry.snapshot()
            report = check_rules(scenario, result, connector.events, completed)
            trace = Trace(scenario.id, agent.version, timestamp(), connector.events, result.evidence,
                          result.decision_summary, result.approval_state, result.actions,
                          {"checks": report["checks"]}, result.outcome, stats["total_wall_clock_ms"],
                          stats["model_call_count"], stats["tool_call_count"], stats["estimated_cost"])
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
                "measurement_scope": "scenario loading, both adapters, checks, scoring and all artifact writes; excludes final timing field update"}
    for filename, data in [("checks", checks), ("score", scores), ("metadata", metadata)]:
        (output / (filename + ".json")).write_text(json.dumps(sanitize(data), indent=2))
    metadata["total_wall_clock_ms"] = (perf_counter() - started) * 1000
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2))
    return output

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = run(args.scenarios, args.output)
    print(output)
    scores = json.loads((output / "score.json").read_text())
    return int(any(s["status"] != "passed" for group in scores.values() for s in group))

if __name__ == "__main__":
    raise SystemExit(main())
