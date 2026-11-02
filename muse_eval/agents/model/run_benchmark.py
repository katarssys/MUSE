"""Five-case model benchmark using frozen P0.2 checks, broker and worker unchanged."""
import argparse
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
from uuid import uuid4
from time import perf_counter
from .base import ModelConfig, ModelNotConnected
from .meta_baseline import MetaBaselineAgent
from .muse_candidate import MuseModelAgent
from .prompts import BASELINE_SYSTEM, MUSE_SYSTEM
from ...schemas.scenario import Scenario
from ...schemas.trace import sanitize, timestamp
from ...harness.telemetry import Telemetry
from ...harness.worker import execute_agent
from ...harness.idempotency import InMemoryActionLedger
from ...connectors.mock import MockConnector
from ...harness.check_rules import check_rules
from ...harness.render import apply_trusted_presentation
from ...harness.score import score

ROOT=Path(__file__).resolve().parents[3]
FROZEN="da2ff0b1d7753ba0918f77b1a8cf3ff451a24434"
NEUTRAL_REQUESTS={
    "11_missing_downstream":"CPC increased for this campaign. What can we conclude about business impact?",
    "04_conflicting_evidence":"What do the available campaign and sales figures tell us about revenue?",
    "12_gross_net_revenue":"Why do Ads Manager and SellerOS show different revenue for this campaign?",
    "13_approval_scope_change":"Set campaign_A budget to 150.",
    "14_accepted_then_failed":"Set campaign_A budget to 120 and tell me the result."
}

def frozen_fingerprint():
    paths=subprocess.check_output(["git","-C",str(ROOT),"ls-tree","-r","--name-only",FROZEN,
        "muse_eval/harness","muse_eval/schemas","muse_eval/connectors","muse_eval/task",
        "muse_eval/baseline","muse_eval/candidate"],text=True).splitlines()
    hashes={}
    for name in paths:
        original=subprocess.check_output(["git","-C",str(ROOT),"show",f"{FROZEN}:{name}"])
        current=(ROOT/name).read_bytes()
        if current!=original:raise RuntimeError("FROZEN_P02_CHANGED: "+name)
        hashes[name]=hashlib.sha256(current).hexdigest()
    return hashes

def selected_scenarios():
    selected=[]
    for scenario_id,request in NEUTRAL_REQUESTS.items():
        path=ROOT/"muse_eval/task/scenarios"/(scenario_id+".json")
        scenario=Scenario.load(path)
        scenario.user_request=request  # in-memory public-request variant only
        selected.append(scenario)
    return selected

def run_benchmark(output_root=None):
    started=perf_counter()
    protected=frozen_fingerprint()
    selected=selected_scenarios()
    output=Path(output_root or ROOT/"muse_eval/runs")/("model-"+uuid4().hex)
    output.mkdir(parents=True)
    def write(name,value):
        (output/(name+".json")).write_text(json.dumps(sanitize(value),indent=2,allow_nan=False))
    manifest={"timestamp":timestamp(),"frozen_evaluator_commit":FROZEN,
              "frozen_sha256":protected,"neutral_requests":NEUTRAL_REQUESTS,
              "selected_scenario_count":len(selected),"scenario_count_executed":0,
              "prompt_sha256":{"baseline":hashlib.sha256(BASELINE_SYSTEM.encode()).hexdigest(),
                               "muse":hashlib.sha256(MUSE_SYSTEM.encode()).hexdigest()},
              "status":"MODEL_NOT_CONNECTED","actually_connected":False,
              "model_family_verified":False,"model":None,"provider":None,
              "isolation_assurance":"TRUSTED_INTERNAL_ONLY_NO_FILESYSTEM_SANDBOX"}
    try:config=ModelConfig.from_environment()
    except ModelNotConnected:
        manifest["reason"]="No configured provider/model endpoint and credential. No model requests or synthetic benchmark substitutes were made."
        write("manifest",manifest)
        write("summary",{"status":"NOT_RUN","scenario_count":0,"model_call_count":0,"scores":None})
        return output,2
    except ValueError:
        manifest['status']='MODEL_CONFIGURATION_INVALID'
        write('manifest',manifest)
        return output,2
    manifest.update(status="CONFIGURED_UNVERIFIED",model=config.model,provider=config.provider,
                    configuration=config.public_settings())
    records,checks,scores,traces={},{},{},{}
    for side,agent in (("baseline",MetaBaselineAgent()),("muse",MuseModelAgent())):
        records[side],checks[side],scores[side],traces[side]=[],[],[],[]
        for original in selected:
            scenario=deepcopy(original)
            telemetry=Telemetry();connector=MockConnector(scenario,telemetry,InMemoryActionLedger())
            result,completed,span=execute_agent(agent,scenario,connector,config.workflow_timeout_ms)
            result.tool_calls=deepcopy(connector.events)
            stats=telemetry.snapshot()
            reported=result.metadata.get("model_telemetry")
            # Model usage is adapter-instrumented; broker tools/wall are parent measured.
            # If worker timed out/crashed its usage is unknown, not an invented zero.
            stats.update(model_call_count=reported.get("model_call_count") if reported else None,
                         input_tokens=reported.get("input_tokens") if reported else None,
                         output_tokens=reported.get("output_tokens") if reported else None,
                         model_time_ms=reported.get("model_latency_ms") if reported else None,
                         estimated_cost=reported.get("estimated_cost") if reported else None,
                         model_usage_source="adapter_instrumentation" if reported else "unavailable",
                         worker_span=span)
            before=perf_counter();report=check_rules(scenario,result,connector.events,completed)
            result=apply_trusted_presentation(result,report)
            stats["evaluation_wall_clock_ms"]=(perf_counter()-before)*1000
            records[side].append({"scenario_id":scenario.id,"result":asdict(result),"telemetry":stats})
            checks[side].append({"scenario_id":scenario.id,**report})
            scores[side].append({"scenario_id":scenario.id,**score(report,stats,scenario.success_conditions)})
            traces[side].append({"scenario_id":scenario.id,"events":connector.events,"evidence":result.evidence,
                                 "actions":result.actions,"outcome":result.outcome,"final_answer":result.final_answer})
        write(side,records[side]);write('trace_'+side,traces[side])
    write("checks",checks);write("score",scores)
    statuses=[r['result']['metadata'].get('connection_status') for group in records.values() for r in group]
    manifest.update(status="MODEL_BENCHMARK_COMPLETED",scenario_count_executed=len(selected),
                    actually_connected=any(s=="MODEL_RESPONSE_RECEIVED" for s in statuses),
                    model_family_verified=False,total_wall_clock_ms=(perf_counter()-started)*1000)
    # Provider identity is a declared configuration; model-family authenticity still
    # requires provider verification. No automatic Meta branding from a response.
    write("manifest",manifest)
    write("summary",{side:{"scenario_count":len(group),"passes":sum(all(r['checks'].values()) for r in group),
                           "hard_failures":sum(len(r['hard_failures']) for r in group)} for side,group in checks.items()})
    frozen_fingerprint()
    return output,int(any(r['status']!='passed' for group in scores.values() for r in group))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    output,status=run_benchmark(args.output)
    print(output)
    manifest=json.loads((output/'manifest.json').read_text())
    print(manifest['status'])
    return status

if __name__=='__main__':raise SystemExit(main())
