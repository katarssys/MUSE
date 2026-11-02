"""Bounded provider-neutral tool loop. Only public TaskContext reaches prompts."""
from dataclasses import asdict
import hashlib
import math
import json
from time import perf_counter
from ...schemas.result import AgentResult
from .base import ModelNotConnected, ModelProviderError
from .provider import ChatCompletionsClient
from .parser import parse_decision, decision_schema, InvalidModelOutput
from .prompts import TOOL_SPECS

class ModelAgent:
    system_prompt = ""
    version = "MODEL_ADAPTER"

    def __init__(self, client=None):
        self.client=client

    def apply(self,context):
        started=perf_counter()
        usage={"source":"adapter_instrumentation","model_call_count":0,"input_tokens":0,"output_tokens":0,
               "model_latency_ms":0.0,"tool_call_count":0,"estimated_cost":None,"provider_usage_available":True}
        def finish(result,status):
            usage["agent_wall_clock_ms"]=(perf_counter()-started)*1000
            result.metadata={"adapter_status":self.version,"connection_status":status,"model_telemetry":usage}
            return result
        try:
            client=self.client or ChatCompletionsClient.from_environment()
        except ModelNotConnected:
            usage.update(input_tokens=None,output_tokens=None,provider_usage_available=False)
            return finish(AgentResult("",outcome="error"),"MODEL_NOT_CONNECTED")
        except ValueError:
            return finish(AgentResult("",outcome="error"),"MODEL_CONFIGURATION_INVALID")
        config=client.config
        allowed=[name for name in context.available_tools if name in TOOL_SPECS]
        schema=decision_schema(allowed)
        # Public development IDs contain scenario names; use opaque aliases so neutral
        # prompts do not accidentally reveal task families through workflow/receipt IDs.
        aliases={}
        def opaque(value):
            key="ref-"+hashlib.sha256(value.encode()).hexdigest()[:24]
            aliases[key]=value
            return key
        public_state={k:v for k,v in context.initial_state.items() if k in
                      {"budget","requested_budget","resource_id","workflow_id","request_repetitions"}}
        public_state['workflow_id']=opaque(str(public_state.get('workflow_id',context.scenario_id)))
        def observation_view(value):
            if isinstance(value,dict):
                return {k:opaque(v) if k in {'receipt_id','workflow_id'} and isinstance(v,str) else observation_view(v)
                        for k,v in value.items()}
            if isinstance(value,list):return [observation_view(v) for v in value]
            return value
        public={"user_request":context.user_request,"initial_state":public_state,
                "available_tools":{name:TOOL_SPECS[name] for name in allowed},"output_schema":schema,
                "limits":{"max_model_calls":config.max_model_calls,"max_tool_calls":config.max_tool_calls}}
        messages=[{"role":"system","content":self.system_prompt},{"role":"user","content":json.dumps(public,allow_nan=False)}]
        for _ in range(config.max_model_calls):
            remaining=config.workflow_timeout_ms/1000-(perf_counter()-started)
            if remaining<=0:return finish(AgentResult("",outcome="error"),"MODEL_TIMEOUT")
            if len(json.dumps(messages))>config.max_context_chars:
                return finish(AgentResult("",outcome="error"),"MODEL_CONTEXT_LIMIT")
            before=perf_counter();usage['model_call_count']+=1
            try:
                response=client.generate(messages,schema,timeout_s=min(config.request_timeout_s,remaining))
            except (ModelProviderError,TimeoutError,OSError) as exc:
                usage['model_latency_ms']+=(perf_counter()-before)*1000
                usage.update(input_tokens=None,output_tokens=None,provider_usage_available=False)
                if isinstance(exc,ModelProviderError):
                    usage['provider_error']=exc.safe_diagnostics()
                return finish(AgentResult("",outcome="error"),"MODEL_PROVIDER_ERROR")
            usage['model_latency_ms']+=(perf_counter()-before)*1000
            for key in ('input_tokens','output_tokens'):
                value=(response.usage or {}).get(key)
                if type(value) is not int or value<0:
                    usage[key]=None;usage['provider_usage_available']=False
                elif usage[key] is not None:usage[key]+=value
            cost=response.estimated_cost
            if type(cost) in (int,float) and math.isfinite(cost) and cost>=0:
                if usage['model_call_count']==1:usage['estimated_cost']=cost
                elif usage['estimated_cost'] is not None:usage['estimated_cost']+=cost
            else:usage['estimated_cost']=None
            if perf_counter()-started>config.workflow_timeout_ms/1000:
                return finish(AgentResult("",outcome="error"),"MODEL_TIMEOUT")
            try:decision=parse_decision(response,allowed)
            except InvalidModelOutput:
                return finish(AgentResult("",outcome="error"),"MODEL_OUTPUT_INVALID")
            if decision['kind']=='final':
                final=decision['result']
                for action in final.actions:
                    action['receipt_ref']=aliases.get(action['receipt_ref'],action['receipt_ref'])
                for claim in final.evidence:
                    if claim['metric'] in {'receipt_id','workflow_id'} and isinstance(claim['value'],str):
                        claim['value']=aliases.get(claim['value'],claim['value'])
                return finish(final,"MODEL_RESPONSE_RECEIVED")
            if usage['tool_call_count']>=config.max_tool_calls:
                return finish(AgentResult("",outcome="error"),"MODEL_TOOL_LIMIT")
            observation=context.tools.call(decision['tool'],decision['args'])
            usage['tool_call_count']+=1
            # Only structured public tool decisions/observations are retained in memory;
            # no raw model prose or private reasoning is persisted.
            messages.append({"role":"assistant","content":json.dumps({"decision":decision},allow_nan=False)})
            messages.append({"role":"user","content":json.dumps({"tool_observation":observation_view(asdict(observation))},allow_nan=False)})
        return finish(AgentResult("",outcome="error"),"MODEL_CALL_LIMIT")
