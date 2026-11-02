"""Shared structural protocol guards, using only public tool capabilities/history.

No scenario, expected result, required evidence, predicate or fixture access.
Rejections request another model decision; they never generate tools or claims.
"""
from copy import deepcopy
from .prompts import TOOL_SPECS

FEEDBACK = {
    'READ_BEFORE_UNKNOWN':'Select and attempt a relevant available read tool before concluding insufficient_data or UNKNOWN. You choose the relevant source.',
    'UNKNOWN_REFERENCE_REQUIRED':'Cite the actual failed/missing observation evidence_ref for UNKNOWN; do not invent a reference or remove an honest claim to conceal uncertainty.',
    'EVIDENCE_REFERENCE_INVALID':'Use only exact source_refs returned by actual tool observations.',
    'EVIDENCE_FIELD_MISMATCH':'A FACT/SIGNAL must use the source tool as subject and an exact data key, value and type from its cited observation. Do not rename fields or invent supporting facts.',
    'WRITE_READBACK_REQUIRED':'A submitted write still needs a same-resource readback attempt through an available verification tool before finalization. You select the appropriate query and classify its result.',
    'PROPOSAL_REQUIRED':'Obtain a proposal/authorization for the exact target before submitting this write.',
    'APPROVAL_REQUIRED':'This proposal requires approval or has no usable approval ID. Do not execute; acquire other relevant evidence or return an honest approval handoff.',
    'APPROVAL_SCOPE_MISMATCH':'Use the exact applicable proposal approval ID and scope; do not invent or rewrite authorization.',
    'EXECUTION_ACTIONS_ONLY':'A proposal is not an execution. Keep proposals as observations, not entries in the execution actions list.',
}

class OrchestrationGuard:
    def __init__(self, available_tools):
        self.available=set(available_tools)
        self.read_tools={name for name in self.available if TOOL_SPECS[name].get('effect')=='read'}
        self.records=[]

    def observe(self, name, args, result):
        self.records.append({'name':name,'args':deepcopy(args),'result':deepcopy(result)})

    @staticmethod
    def same_scope(left, right, spec):
        # Routing scope comes from the public tool input contract, not a scenario.
        keys=set(spec['parameters'])-{'approval_id','idempotency_key'}
        return all(k in left and k in right and type(left[k]) is type(right[k]) and left[k]==right[k] for k in keys)

    def tool_rejection(self, decision):
        spec=TOOL_SPECS[decision['tool']]
        approval_tool=spec.get('approval_tool')
        if spec.get('effect')!='write' or approval_tool not in self.available:
            return None
        proposals=[r for r in self.records if r['name']==approval_tool and self.same_scope(r['args'],decision['args'],spec)]
        if not proposals:return 'PROPOSAL_REQUIRED'
        response=proposals[-1]['result']
        data=response['data']
        approval=data.get('approval_id')
        if not response['success'] or data.get('status')=='approval_required' or not isinstance(approval,str) or not approval.strip():
            return 'APPROVAL_REQUIRED'
        if decision['args'].get('approval_id')!=approval:return 'APPROVAL_SCOPE_MISMATCH'
        return None

    def needs_readback(self):
        for i,record in enumerate(self.records):
            spec=TOOL_SPECS[record['name']]
            result=record['result'];data=result['data']
            verifiers=set(spec.get('verification_tools',[])) & self.read_tools
            if (spec.get('effect')!='write' or not result['success'] or not verifiers
                    or data.get('status') in {'verified','failed'}):
                continue
            satisfied=False
            for later in self.records[i+1:]:
                if later['name'] not in verifiers:continue
                if later['args'].get('resource_id')!=record['args'].get('resource_id'):continue
                observed=later['result']['data']
                if observed.get('resource_id',record['args'].get('resource_id'))!=record['args'].get('resource_id'):continue
                if any(key in data and key in observed and data[key]!=observed[key] for key in ('receipt_id','workflow_id')):continue
                # A failed read is an attempt, not proof of a successful write.
                # Final state classification and its claims still belong to the model.
                satisfied=True
                break
            if not satisfied:return True
        return False

    def final_rejection(self, result):
        if self.needs_readback():return 'WRITE_READBACK_REQUIRED'
        attempted_reads=[r for r in self.records if r['name'] in self.read_tools]
        unknowns=[c for c in result.evidence if c['type']=='unknown']
        if (result.outcome=='insufficient_data' or unknowns) and self.read_tools and not attempted_reads:
            return 'READ_BEFORE_UNKNOWN'
        refs={r['result']['metadata'].get('evidence_ref'):r for r in self.records}
        for claim in result.evidence:
            sources=claim['source_refs']
            if claim['type']=='unknown' and self.read_tools and not sources:
                return 'UNKNOWN_REFERENCE_REQUIRED'
            if any(ref not in refs for ref in sources):return 'EVIDENCE_REFERENCE_INVALID'
            if claim['type']=='metric' and claim['certainty'] in {'FACT','SIGNAL'}:
                if not sources or not any(
                    refs[ref]['result']['success'] and refs[ref]['name']==claim['subject']
                    and claim['metric'] in refs[ref]['result']['data']
                    and type(refs[ref]['result']['data'][claim['metric']]) is type(claim['value'])
                    and refs[ref]['result']['data'][claim['metric']]==claim['value'] for ref in sources):
                    return 'EVIDENCE_FIELD_MISMATCH'
        if any(a['status']=='PROPOSED' for a in result.actions):return 'EXECUTION_ACTIONS_ONLY'
        return None

    def rejection(self, decision):
        return self.tool_rejection(decision) if decision['kind']=='tool' else self.final_rejection(decision['result'])
