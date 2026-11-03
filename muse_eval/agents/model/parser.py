"""Strict model protocol. Never repairs model claims using evaluator information."""
from copy import deepcopy
import json
from ...schemas.result import validate_result
from .prompts import OUTCOMES, TOOL_SPECS

class InvalidModelOutput(ValueError):
    pass

CLAIM_SCHEMA={"type":"object","additionalProperties":False,"properties":{
    "type":{"type":"string","enum":["metric","hypothesis","unknown"]},"subject":{"type":"string"},
    "metric":{"type":"string"},"value":{"type":["string","number","boolean","null"]},
    "source_refs":{"type":"array","items":{"type":"string"}},
    "certainty":{"type":"string","enum":["FACT","SIGNAL","INFERENCE","HYPOTHESIS","UNKNOWN"]}},
    "required":["type","subject","metric","value","source_refs","certainty"]}
ACTION_SCHEMA={"type":"object","additionalProperties":False,"properties":{
    "action_type":{"type":"string","enum":["execute_budget_change"]},"resource":{"type":"string"},
    "requested_parameters":{"type":"object","additionalProperties":False,"properties":{"budget":{"type":"number"}},"required":["budget"]},
    "status":{"type":"string","enum":["PROPOSED","ACCEPTED","EXECUTED","VERIFIED","FAILED"]},
    "receipt_ref":{"type":["string","null"]}},"required":["action_type","resource","requested_parameters","status","receipt_ref"]}
FINAL_SCHEMA={"type":"object","additionalProperties":False,"properties":{
    "outcome":{"type":"string","enum":OUTCOMES},"evidence":{"type":"array","items":CLAIM_SCHEMA},
    "actions":{"type":"array","items":ACTION_SCHEMA},
    "approval_state":{"type":"string","enum":["not_required","pending","approved"]},"decision_summary":{"type":"string"}},
    "required":["outcome","evidence","actions","approval_state","decision_summary"]}

def decision_schema(available_tools, *, allow_final=True):
    # Both agents receive exactly the same discriminated output schema.
    # The first live decision can be narrowed to tool-only when tools exist;
    # after an observation, finalization becomes available again.
    branches=[]
    for name in available_tools:
        parameters=TOOL_SPECS[name]["parameters"]
        args={"type":"object","additionalProperties":False,"properties":{k:{"type":v} for k,v in parameters.items()},"required":list(parameters)}
        branches.append({"type":"object","additionalProperties":False,"properties":{
            "kind":{"type":"string","enum":["tool"]},"tool":{"type":"string","enum":[name]},"args":args},"required":["kind","tool","args"]})
    if allow_final or not branches:
        branches.append({"type":"object","additionalProperties":False,"properties":{
            "kind":{"type":"string","enum":["final"]},"result":FINAL_SCHEMA},"required":["kind","result"]})
    return {"type":"object","additionalProperties":False,
            "properties":{"decision":{"anyOf":branches}},"required":["decision"]}

def _strict_keys(value,keys):
    if not isinstance(value,dict) or set(value)!=set(keys):
        raise InvalidModelOutput("MODEL_OUTPUT_INVALID")

def _no_duplicates(pairs):
    obj={}
    for k,v in pairs:
        if k in obj: raise InvalidModelOutput("MODEL_OUTPUT_INVALID")
        obj[k]=v
    return obj

def parse_decision(response,available_tools):
    try:
        if response.structured_output is not None:
            value=json.loads(json.dumps(response.structured_output,allow_nan=False),object_pairs_hook=_no_duplicates)
        else:
            value=json.loads(response.text,parse_constant=lambda x: (_ for _ in ()).throw(InvalidModelOutput("MODEL_OUTPUT_INVALID")),object_pairs_hook=_no_duplicates)
        _strict_keys(value,{"decision"})
        value=value["decision"]
        if not isinstance(value,dict):raise InvalidModelOutput("MODEL_OUTPUT_INVALID")
        if value.get("kind")=="tool":
            _strict_keys(value,{"kind","tool","args"})
            name=value["tool"]
            if name not in available_tools or name not in TOOL_SPECS:raise InvalidModelOutput("MODEL_OUTPUT_INVALID")
            args=value["args"];types=TOOL_SPECS[name]["parameters"]
            _strict_keys(args,types)
            for k,t in types.items():
                if t=="string" and not isinstance(args[k],str):raise InvalidModelOutput("MODEL_OUTPUT_INVALID")
                if t=="number" and (type(args[k]) not in (int,float) or args[k]<=0):raise InvalidModelOutput("MODEL_OUTPUT_INVALID")
            return deepcopy(value)
        _strict_keys(value,{"kind","result"})
        if value["kind"]!="final":raise InvalidModelOutput("MODEL_OUTPUT_INVALID")
        data=value["result"]
        _strict_keys(data,{"outcome","evidence","actions","approval_state","decision_summary"})
        if data['outcome'] not in OUTCOMES or data['approval_state'] not in {'not_required','pending','approved'}:
            raise InvalidModelOutput("MODEL_OUTPUT_INVALID")
        result=validate_result({"final_answer":"",**data})
        # Extra output validation without changing frozen evaluator.
        for claim in result.evidence:
            if type(claim["value"]) not in (str,int,float,bool,type(None)):
                raise InvalidModelOutput("MODEL_OUTPUT_INVALID")
        for action in result.actions:
            budget=action['requested_parameters'].get('budget')
            if set(action['requested_parameters'])!={'budget'} or type(budget) not in (int,float) or budget<=0:
                raise InvalidModelOutput("MODEL_OUTPUT_INVALID")
        return {"kind":"final","result":result}
    except (ValueError,TypeError,KeyError,AttributeError):
        raise InvalidModelOutput("MODEL_OUTPUT_INVALID") from None
