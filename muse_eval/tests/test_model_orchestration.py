"""Generic model protocol tests; scripted decisions, no live inference or solver."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest

from muse_eval.agents.model.base import ModelConfig, ModelResponse
from muse_eval.agents.model.meta_baseline import MetaBaselineAgent
from muse_eval.agents.model.muse_candidate import MuseModelAgent
from muse_eval.agents.model.orchestration import OrchestrationGuard
from muse_eval.agents.model.prompts import BASELINE_SYSTEM, MUSE_SYSTEM, TOOL_SPECS
from muse_eval.agents.model.run_benchmark import frozen_fingerprint
from muse_eval.connectors.base import ToolResult
from muse_eval.schemas.result import TaskContext
from muse_eval.harness.check_rules import grounded

CONFIG=ModelConfig('TEST_DOUBLE','not-a-real-model','https://example.invalid/chat/completions')
RESOURCE='shop_A'

def tool(name,**args):
    return {'decision':{'kind':'tool','tool':name,'args':{'resource_id':RESOURCE,**args}}}

def fact(subject,metric,value,ref):
    return {'type':'metric','subject':subject,'metric':metric,'value':value,'certainty':'FACT','source_refs':[ref]}

def unknown(refs):
    return {'type':'unknown','subject':RESOURCE,'metric':'unavailable_source','value':None,'certainty':'UNKNOWN','source_refs':refs}

def final(outcome='insufficient_data',evidence=None,actions=None,approval='not_required'):
    return {'decision':{'kind':'final','result':{'outcome':outcome,'evidence':evidence or [],
            'actions':actions or [],'approval_state':approval,'decision_summary':'Concise public summary.'}}}

class Client:
    def __init__(self,decisions,config=CONFIG):self.decisions=iter(decisions);self.config=config;self.inputs=[]
    def generate(self,messages,schema,*,timeout_s):
        self.inputs.append((deepcopy(messages),deepcopy(schema)))
        value=next(self.decisions)
        return ModelResponse(structured_output=value(messages) if callable(value) else value)

class Tools:
    def __init__(self,responses):self.responses=iter(responses);self.calls=[]
    def call(self,name,args):
        self.calls.append((name,deepcopy(args)))
        response=next(self.responses)
        return deepcopy(response)

def context(tools,available,request='Assess the available business evidence.'):
    return TaskContext('opaque-workflow',request,{'resource_id':RESOURCE,'budget':100},tuple(available),tools)

def read_result(data,ref='obs-1',success=True,error=None):
    return ToolResult(success,data,error,{'evidence_ref':ref})

def proposal(approval='approval-id',status='authorized'):
    return read_result({'resource_id':RESOURCE,'budget':120,'status':status,'approval_id':approval},'proposal-ref')

def receipt():
    return read_result({'resource':RESOURCE,'budget':120,'status':'accepted','receipt_id':'operation-id','workflow_id':'opaque-workflow'},'write-ref')

class ModelOrchestrationTests(unittest.TestCase):
    def test_both_prompts_require_reads_before_insufficient_and_exact_fields(self):
        for prompt in (BASELINE_SYSTEM,MUSE_SYSTEM):
            self.assertIn('Never return insufficient_data',prompt)
            self.assertIn('relevant available read tool',prompt)
            self.assertIn('copy metric exactly',prompt)
            self.assertIn('exact evidence_ref',prompt)
            self.assertIn('Never invent aliases',prompt)
            self.assertIn('UNKNOWN has\nvalue=null',prompt)
            self.assertIn('failed/missing observation',prompt)
        self.assertIn('Do not finalize insufficient_data before',MUSE_SYSTEM)

    def test_premature_unknown_is_rejected_model_selects_read_then_honest_failed_ref(self):
        for cls in (MetaBaselineAgent,MuseModelAgent):
            with self.subTest(adapter=cls.__name__):
                data=Tools([read_result({},'failed-ref',False,'missing_data')])
                decisions=[final(evidence=[unknown([])]),tool('get_sales'),final(evidence=[unknown(['failed-ref'])])]
                client=Client(decisions)
                result=cls(client).apply(context(data,['get_sales']))
                self.assertEqual(data.calls,[('get_sales',{'resource_id':RESOURCE})])
                self.assertEqual(result.metadata['model_telemetry']['orchestration_feedback_codes'],['READ_BEFORE_UNKNOWN'])
                self.assertEqual(result.metadata['model_telemetry']['model_call_count'],3)
                self.assertEqual(result.evidence,[unknown(['failed-ref'])])
                self.assertEqual(result.metadata['connection_status'],'MODEL_RESPONSE_RECEIVED')
                # Frozen grounding intentionally does NOT accept failed-call refs.
                # The agent must not substitute a fabricated successful citation.
                self.assertFalse(grounded(result.evidence[0],{}))

    def test_unknown_empty_ref_after_failed_read_requests_model_citation(self):
        data=Tools([read_result({},'failed-ref',False,'missing_data')])
        client=Client([tool('get_sales'),final(evidence=[unknown([])]),final(evidence=[unknown(['failed-ref'])])])
        result=MuseModelAgent(client).apply(context(data,['get_sales']))
        self.assertEqual(result.metadata['model_telemetry']['orchestration_feedback_codes'],['UNKNOWN_REFERENCE_REQUIRED'])
        self.assertEqual(result.evidence[0]['source_refs'],['failed-ref'])

    def test_no_available_read_source_does_not_trigger_automatic_calls(self):
        data=Tools([]);result=MuseModelAgent(Client([final(evidence=[unknown([])])])).apply(context(data,[]))
        self.assertEqual(result.metadata['connection_status'],'MODEL_RESPONSE_RECEIVED')
        self.assertEqual(data.calls,[])

    def test_guard_does_not_choose_a_read_tool_or_increase_budgets(self):
        data=Tools([]);config=replace(CONFIG,max_model_calls=2)
        result=MuseModelAgent(Client([final(),final()],config)).apply(context(data,['get_sales','get_margin']))
        self.assertEqual(data.calls,[])
        self.assertEqual(result.metadata['connection_status'],'MODEL_CALL_LIMIT')
        self.assertEqual(result.metadata['model_telemetry']['model_call_count'],2)
        self.assertEqual(result.metadata['model_telemetry']['orchestration_rejections'],2)

    def test_alias_is_rejected_not_silently_renamed(self):
        data=Tools([read_result({'revenue':1000,'revenue_delta':0,'resource_id':RESOURCE})])
        bad=fact('get_sales','sales_revenue',1000,'obs-1');before=deepcopy(bad)
        good=fact('get_sales','revenue',1000,'obs-1')
        client=Client([tool('get_sales'),final('conflicting_evidence',[bad]),final('conflicting_evidence',[good])])
        result=MuseModelAgent(client).apply(context(data,['get_sales']))
        self.assertEqual(bad,before)
        self.assertEqual(result.evidence,[good])
        self.assertEqual(result.metadata['model_telemetry']['orchestration_feedback_codes'],['EVIDENCE_FIELD_MISMATCH'])
        feedback=client.inputs[-1][0][-1]['content']
        self.assertNotIn('sales_revenue',feedback)
        self.assertNotIn('revenue_delta',feedback)
        self.assertEqual(len(data.calls),1)

    def test_exact_value_type_and_source_are_required_without_fact_repair(self):
        guard=OrchestrationGuard(['get_sales'])
        guard.observe('get_sales',{'resource_id':RESOURCE},read_result({'revenue':1000}).__dict__)
        from muse_eval.agents.model.parser import parse_decision
        for bad in (fact('get_sales','revenue',999,'obs-1'),fact('get_sales','revenue',1000.0,'obs-1'),
                    fact(RESOURCE,'revenue',1000,'obs-1'),fact('get_sales','revenue',1000,'invented')):
            with self.subTest(claim=bad):
                decision=parse_decision(ModelResponse(structured_output=final('conflicting_evidence',[bad])),['get_sales'])
                self.assertIsNotNone(guard.rejection(decision))
                self.assertEqual(decision['result'].evidence,[bad])

    def test_accepted_write_requires_readback_before_final_for_both_agents(self):
        for cls in (MetaBaselineAgent,MuseModelAgent):
            with self.subTest(adapter=cls.__name__):
                tools=Tools([proposal(),receipt(),read_result({'resource_id':RESOURCE,'current_budget':100,
                    'receipt_id':'operation-id','operation_status':'failed'},'readback-ref')])
                def failed(messages):
                    observed=json.loads(messages[-1]['content'])['tool_observation']['data']
                    action={'action_type':'execute_budget_change','resource':RESOURCE,'requested_parameters':{'budget':120},
                            'status':'FAILED','receipt_ref':observed['receipt_id']}
                    return final('verification_failed',actions=[action],approval='approved')
                client=Client([tool('propose_budget_change',budget=120,idempotency_key='operation'),
                               tool('execute_budget_change',budget=120,idempotency_key='operation',approval_id='approval-id'),
                               final('pending_verification'),tool('get_campaign_metrics'),failed])
                result=cls(client).apply(context(tools,['propose_budget_change','execute_budget_change','get_campaign_metrics']))
                self.assertEqual([name for name,_ in tools.calls],['propose_budget_change','execute_budget_change','get_campaign_metrics'])
                self.assertEqual(result.outcome,'verification_failed')
                self.assertEqual(result.actions[0]['status'],'FAILED')
                self.assertEqual(result.actions[0]['receipt_ref'],'operation-id')
                self.assertEqual(result.metadata['model_telemetry']['orchestration_feedback_codes'],['WRITE_READBACK_REQUIRED'])

    def test_readback_must_match_resource_and_receipt_when_present(self):
        guard=OrchestrationGuard(['execute_budget_change','get_campaign_metrics'])
        guard.observe('execute_budget_change',{'resource_id':RESOURCE,'budget':120},receipt().__dict__)
        guard.observe('get_campaign_metrics',{'resource_id':'other'},read_result({'resource_id':'other'}).__dict__)
        self.assertTrue(guard.needs_readback())
        guard.observe('get_campaign_metrics',{'resource_id':RESOURCE},read_result({'resource_id':RESOURCE,'receipt_id':'wrong'}).__dict__)
        self.assertTrue(guard.needs_readback())
        guard.observe('get_campaign_metrics',{'resource_id':RESOURCE},read_result({'resource_id':RESOURCE,'receipt_id':'operation-id','operation_status':'pending'}).__dict__)
        self.assertFalse(guard.needs_readback())

    def test_guard_does_not_map_observed_failure_to_an_expected_outcome(self):
        from muse_eval.agents.model.parser import parse_decision
        guard=OrchestrationGuard(['execute_budget_change','get_campaign_metrics'])
        guard.observe('execute_budget_change',{'resource_id':RESOURCE,'budget':120},receipt().__dict__)
        guard.observe('get_campaign_metrics',{'resource_id':RESOURCE},
                      read_result({'resource_id':RESOURCE,'receipt_id':'operation-id','operation_status':'failed'}).__dict__)
        decision=parse_decision(ModelResponse(structured_output=final('action_failed')),[])
        self.assertIsNone(guard.rejection(decision))
        self.assertEqual(decision['result'].outcome,'action_failed')

    def test_readback_attempt_can_fail_without_manufacturing_success(self):
        guard=OrchestrationGuard(['execute_budget_change','get_campaign_metrics'])
        guard.observe('execute_budget_change',{'resource_id':RESOURCE,'budget':120},receipt().__dict__)
        guard.observe('get_campaign_metrics',{'resource_id':RESOURCE},read_result({},'read-error',False,'read_failed').__dict__)
        self.assertFalse(guard.needs_readback())
        # Only the attempt obligation is fulfilled; no state/claim is synthesized.
        self.assertFalse(guard.records[-1]['result']['success'])

    def test_approval_required_or_missing_id_blocks_execution_and_preserves_proposal_facts(self):
        for status,approval_id in [('approval_required',None),('authorized',None)]:
            with self.subTest(status=status):
                tools=Tools([proposal(approval_id,status)])
                facts=[fact('propose_budget_change','status',status,'proposal-ref'),
                       fact('propose_budget_change','approval_id',approval_id,'proposal-ref')]
                client=Client([tool('propose_budget_change',budget=120,idempotency_key='operation'),
                               tool('execute_budget_change',budget=120,idempotency_key='operation',approval_id='invented'),
                               final('awaiting_approval',facts,approval='pending')])
                result=MuseModelAgent(client).apply(context(tools,['propose_budget_change','execute_budget_change','get_campaign_metrics']))
                self.assertEqual([name for name,_ in tools.calls],['propose_budget_change'])
                self.assertEqual(result.actions,[])
                self.assertEqual(result.evidence,facts)
                self.assertEqual(result.metadata['model_telemetry']['orchestration_feedback_codes'],['APPROVAL_REQUIRED'])
                self.assertEqual(result.outcome,'awaiting_approval')
                self.assertFalse(grounded(facts[0],{'proposal-ref':{'selected_tool':'propose_budget_change',
                    'tool_result':proposal(approval_id,status).__dict__}}))

    def test_wrong_approval_scope_is_not_rewritten(self):
        tools=Tools([proposal()])
        wrong=tool('execute_budget_change',budget=150,idempotency_key='operation',approval_id='approval-id')
        before=deepcopy(wrong)
        client=Client([tool('propose_budget_change',budget=120,idempotency_key='operation'),wrong,final('awaiting_approval')])
        result=MuseModelAgent(client).apply(context(tools,['propose_budget_change','execute_budget_change']))
        self.assertEqual(wrong,before)
        self.assertEqual(result.metadata['model_telemetry']['orchestration_feedback_codes'],['PROPOSAL_REQUIRED'])
        self.assertEqual(len(tools.calls),1)

    def test_proposal_is_not_an_execution_action(self):
        tools=Tools([proposal(None,'approval_required')])
        proposed={'action_type':'execute_budget_change','resource':RESOURCE,'requested_parameters':{'budget':120},
                  'status':'PROPOSED','receipt_ref':None}
        client=Client([tool('propose_budget_change',budget=120,idempotency_key='operation'),
                       final('awaiting_approval',actions=[proposed],approval='pending'),
                       final('awaiting_approval',approval='pending')])
        result=MuseModelAgent(client).apply(context(tools,['propose_budget_change','execute_budget_change']))
        self.assertEqual(result.actions,[])
        self.assertEqual(result.metadata['model_telemetry']['orchestration_feedback_codes'],['EXECUTION_ACTIONS_ONLY'])
        self.assertEqual(len(tools.calls),1)

    def test_readback_guard_uses_tool_capabilities_not_benchmark_names(self):
        from unittest.mock import patch
        capabilities={
            'submit_inventory':{'effect':'write','parameters':{'resource_id':'string','quantity':'number'},
                                'verification_tools':['read_inventory']},
            'read_inventory':{'effect':'read','parameters':{'resource_id':'string'}}}
        with patch.dict(TOOL_SPECS,capabilities):
            guard=OrchestrationGuard(capabilities)
            guard.observe('submit_inventory',{'resource_id':'warehouse','quantity':3},
                          read_result({'status':'queued','receipt_id':'inventory-receipt'}).__dict__)
            self.assertTrue(guard.needs_readback())
            guard.observe('read_inventory',{'resource_id':'warehouse'},
                          read_result({'resource_id':'warehouse','receipt_id':'inventory-receipt','quantity':3}).__dict__)
            self.assertFalse(guard.needs_readback())

    def test_same_schema_tools_limits_and_protocol_for_both_agents(self):
        clients=[]
        for cls in (MetaBaselineAgent,MuseModelAgent):
            tools=Tools([read_result({'revenue':1000})]);client=Client([tool('get_sales'),final('conflicting_evidence')])
            cls(client).apply(context(tools,['get_sales','get_margin']))
            clients.append(client)
        self.assertEqual(clients[0].config,clients[1].config)
        self.assertEqual(clients[0].inputs[0][1],clients[1].inputs[0][1])
        self.assertEqual(clients[0].inputs[0][0][1],clients[1].inputs[0][0][1])
        self.assertNotEqual(clients[0].inputs[0][0][0],clients[1].inputs[0][0][0])

    def test_prompts_and_guards_have_no_benchmark_lookup_or_alias_mapping(self):
        import inspect
        from muse_eval.agents.model import orchestration
        text=BASELINE_SYSTEM+MUSE_SYSTEM+inspect.getsource(orchestration)
        for forbidden in ('11_missing_downstream','12_gross_net_revenue','14_accepted_then_failed',
                          'expected_outcome','success_conditions','required_evidence','sales_revenue','attribution_source','sales_sufficient'):
            self.assertNotIn(forbidden,text)
        self.assertNotIn('from ...harness',inspect.getsource(orchestration))
        self.assertNotIn('fixture_data',text)
        self.assertEqual(len(frozen_fingerprint()),38)

if __name__=='__main__':unittest.main()
