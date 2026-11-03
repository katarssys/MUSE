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
    def test_muse_strategy_is_separate_from_shared_wire_safety(self):
        self.assertIn('Do not finalize insufficient_data before',MUSE_SYSTEM)
        self.assertIn('relevant available read tool',MUSE_SYSTEM)
        self.assertIn('copy metric exactly',MUSE_SYSTEM)
        self.assertIn('accepted/pending async',MUSE_SYSTEM)
        self.assertIn('distinct states',MUSE_SYSTEM)
        self.assertIn('Stop as soon as the observations already support a terminal decision',MUSE_SYSTEM)
        self.assertIn('downstream observation was attempted and failed or is unavailable',MUSE_SYSTEM)
        self.assertIn('unrelated reads merely to avoid insufficient_data',MUSE_SYSTEM)
        self.assertIn('validity, sufficiency, status, resource identity and state fields',MUSE_SYSTEM)
        self.assertIn('include that exact sufficiency field in evidence',MUSE_SYSTEM)
        self.assertIn('serialize every observed field',MUSE_SYSTEM)
        self.assertIn('both sides of the comparison',MUSE_SYSTEM)
        self.assertIn('observed component used in any arithmetic relationship',MUSE_SYSTEM)
        self.assertIn('observed final/derived',MUSE_SYSTEM)
        self.assertIn('quantity being reconciled',MUSE_SYSTEM)
        self.assertIn('Do not omit a field merely because another',MUSE_SYSTEM)
        self.assertIn('complete observed proof',MUSE_SYSTEM)
        self.assertIn('successful upstream read',MUSE_SYSTEM)
        self.assertIn('finalize insufficient_data instead of calling unrelated reads',MUSE_SYSTEM)
        self.assertIn('proposal observations or write acknowledgements in the evidence',MUSE_SYSTEM)
        self.assertIn('classify it as conflicting_evidence',MUSE_SYSTEM)
        self.assertIn('keep the workflow action-oriented',MUSE_SYSTEM)
        self.assertIn('they do not satisfy or replace',MUSE_SYSTEM)
        self.assertIn('the requested action',MUSE_SYSTEM)
        self.assertIn('call the available proposal',MUSE_SYSTEM)
        self.assertIn('exact requested resource and budget',MUSE_SYSTEM)
        self.assertIn('awaiting_approval with approval_state=pending',MUSE_SYSTEM)
        self.assertIn('Before a campaign budget proposal',MUSE_SYSTEM)
        self.assertIn('readback explicitly reports failure is verification_failed',MUSE_SYSTEM)
        self.assertNotIn('Stop as soon as the observations already support a terminal decision',BASELINE_SYSTEM)
        self.assertNotIn('Before a campaign budget proposal',BASELINE_SYSTEM)
        self.assertNotIn('Do not finalize insufficient_data before',BASELINE_SYSTEM)
        self.assertNotIn('Acquire relevant evidence before concluding',BASELINE_SYSTEM)
        self.assertNotIn('explicit evidence-and-action workflow',BASELINE_SYSTEM)
        self.assertIn('Do not claim verified success',BASELINE_SYSTEM)

    def test_incomplete_final_is_allowed_without_acquisition_retry(self):
        for cls in (MetaBaselineAgent,MuseModelAgent):
            data=Tools([])
            result=cls(Client([final(evidence=[unknown([])])])).apply(context(data,['get_sales']))
            stats=result.metadata['model_telemetry']
            self.assertEqual(result.metadata['connection_status'],'MODEL_RESPONSE_RECEIVED')
            self.assertEqual(stats['model_call_count'],1)
            self.assertEqual(stats['orchestration_rejections'],0)
            self.assertEqual(data.calls,[])

    def test_unknown_empty_ref_after_failed_read_does_not_retry(self):
        data=Tools([read_result({},'failed-ref',False,'missing_data')])
        client=Client([tool('get_sales'),final(evidence=[unknown([])])])
        result=MuseModelAgent(client).apply(context(data,['get_sales']))
        self.assertEqual(result.metadata['model_telemetry']['orchestration_rejections'],0)
        self.assertEqual(result.evidence[0]['source_refs'],[])

    def test_no_available_read_source_does_not_trigger_automatic_calls(self):
        data=Tools([]);result=MuseModelAgent(Client([final(evidence=[unknown([])])])).apply(context(data,[]))
        self.assertEqual(result.metadata['connection_status'],'MODEL_RESPONSE_RECEIVED')
        self.assertEqual(data.calls,[])

    def test_repeated_invalid_ref_stops_before_model_call_limit(self):
        bad=final(evidence=[unknown(['absent'])])
        for cls in (MetaBaselineAgent,MuseModelAgent):
            client=Client([bad]*8);data=Tools([])
            result=cls(client).apply(context(data,['get_sales']))
            stats=result.metadata['model_telemetry']
            self.assertEqual(result.metadata['connection_status'],'MODEL_ORCHESTRATION_BLOCKED')
            self.assertEqual(stats['model_call_count'],2)
            self.assertEqual(stats['orchestration_rejections'],2)
            self.assertEqual([e['no_progress'] for e in stats['orchestration_events']],[False,True])
            self.assertEqual([e['feedback_sent'] for e in stats['orchestration_events']],[True,False])
            self.assertFalse(stats['orchestration_finalization_after_feedback'])
            self.assertEqual(data.calls,[])

    def test_metric_alias_is_not_rejected_or_repaired(self):
        data=Tools([read_result({'revenue':1000})])
        bad=fact('get_sales','sales_revenue',1000,'obs-1');before=deepcopy(bad)
        result=MuseModelAgent(Client([tool('get_sales'),final('conflicting_evidence',[bad])])).apply(context(data,['get_sales']))
        self.assertEqual(bad,before)
        self.assertEqual(result.evidence,[bad])
        self.assertEqual(result.metadata['model_telemetry']['orchestration_rejections'],0)

    def test_semantic_incompleteness_is_allowed_but_nonexistent_ref_is_blocked(self):
        guard=OrchestrationGuard(['get_sales'])
        guard.observe('get_sales',{'resource_id':RESOURCE},read_result({'revenue':1000}).__dict__)
        from muse_eval.agents.model.parser import parse_decision
        for claim in (fact('get_sales','missing',999,'obs-1'),fact('get_sales','revenue',1000.0,'obs-1'),
                      fact(RESOURCE,'revenue',1000,'obs-1')):
            decision=parse_decision(ModelResponse(structured_output=final(evidence=[claim])),['get_sales'])
            self.assertIsNone(guard.rejection(decision))
            self.assertEqual(decision['result'].evidence,[claim])
        decision=parse_decision(ModelResponse(structured_output=final(evidence=[unknown(['invented'])])),[])
        self.assertEqual(guard.rejection(decision),'EVIDENCE_REFERENCE_INVALID')

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
                               final('executed_verified'),tool('get_campaign_metrics'),failed])
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

    def test_proposal_only_final_is_not_semantically_rejected(self):
        tools=Tools([proposal(None,'approval_required')])
        proposed={'action_type':'execute_budget_change','resource':RESOURCE,'requested_parameters':{'budget':120},
                  'status':'PROPOSED','receipt_ref':None}
        client=Client([tool('propose_budget_change',budget=120,idempotency_key='operation'),
                       final('awaiting_approval',actions=[proposed],approval='pending')])
        result=MuseModelAgent(client).apply(context(tools,['propose_budget_change','execute_budget_change']))
        self.assertEqual(result.actions,[proposed])
        self.assertEqual(result.metadata['model_telemetry']['orchestration_rejections'],0)
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

    def test_feedback_can_end_with_imperfect_safe_final(self):
        client=Client([final(evidence=[unknown(['absent'])]),final(evidence=[unknown([])])])
        result=MuseModelAgent(client).apply(context(Tools([]),['get_sales']))
        self.assertEqual(result.metadata['connection_status'],'MODEL_RESPONSE_RECEIVED')
        self.assertEqual(result.metadata['model_telemetry']['model_call_count'],2)
        self.assertTrue(result.metadata['model_telemetry']['orchestration_finalization_after_feedback'])

    def test_changing_rejection_code_without_observation_does_not_reset_bound(self):
        client=Client([final(evidence=[unknown(['absent'])]),
                       tool('execute_budget_change',budget=120,idempotency_key='operation',approval_id='fake')])
        tools=Tools([])
        result=MuseModelAgent(client).apply(context(tools,['propose_budget_change','execute_budget_change']))
        self.assertEqual(result.metadata['connection_status'],'MODEL_ORCHESTRATION_BLOCKED')
        self.assertEqual(result.metadata['model_telemetry']['orchestration_feedback_codes'],
                         ['EVIDENCE_REFERENCE_INVALID','PROPOSAL_REQUIRED'])
        self.assertEqual(tools.calls,[])

    def test_repeated_unauthorized_write_is_never_executed(self):
        write=tool('execute_budget_change',budget=120,idempotency_key='operation',approval_id='fake')
        for available in (['execute_budget_change'],['execute_budget_change','propose_budget_change']):
            data=Tools([]);result=MetaBaselineAgent(Client([write]*8)).apply(context(data,available))
            self.assertEqual(result.metadata['connection_status'],'MODEL_ORCHESTRATION_BLOCKED')
            self.assertEqual(result.metadata['model_telemetry']['model_call_count'],2)
            self.assertEqual(data.calls,[])

    def test_last_available_call_rejection_is_not_model_call_limit(self):
        client=Client([final(evidence=[unknown(['absent'])])],replace(CONFIG,max_model_calls=1))
        result=MuseModelAgent(client).apply(context(Tools([]),[]))
        self.assertEqual(result.metadata['connection_status'],'MODEL_ORCHESTRATION_BLOCKED')
        self.assertFalse(result.metadata['model_telemetry']['orchestration_events'][0]['feedback_sent'])

    def test_new_tool_observation_renews_feedback_allowance(self):
        client=Client([final(evidence=[unknown(['absent'])]),tool('get_sales'),
                       final(evidence=[unknown(['absent'])]),final()])
        data=Tools([read_result({'revenue':10})])
        result=MuseModelAgent(client).apply(context(data,['get_sales']))
        stats=result.metadata['model_telemetry']
        self.assertEqual(result.metadata['connection_status'],'MODEL_RESPONSE_RECEIVED')
        self.assertEqual([e['no_progress'] for e in stats['orchestration_events']],[False,False])
        self.assertEqual(stats['model_call_count'],4)

    def test_ordinary_baseline_multi_tool_async_workflow_has_no_feedback(self):
        data=Tools([read_result({'budget':100}),proposal(),receipt(),
                    read_result({'resource_id':RESOURCE,'operation_status':'failed'},'readback')])
        client=Client([tool('get_campaign_metrics'),
                       tool('propose_budget_change',budget=120,idempotency_key='operation'),
                       tool('execute_budget_change',budget=120,idempotency_key='operation',approval_id='approval-id'),
                       tool('get_campaign_metrics'),final('verification_failed')])
        result=MetaBaselineAgent(client).apply(context(data,['get_campaign_metrics','propose_budget_change','execute_budget_change']))
        self.assertEqual(len(data.calls),4)
        self.assertEqual(result.outcome,'verification_failed')
        self.assertEqual(result.metadata['model_telemetry']['orchestration_rejections'],0)
        self.assertEqual(result.metadata['model_telemetry']['model_call_count'],5)
        self.assertEqual(client.config.max_model_calls,8)

    def test_pending_final_without_verified_claim_does_not_force_readback(self):
        data=Tools([proposal(),receipt()])
        client=Client([tool('propose_budget_change',budget=120,idempotency_key='operation'),
                       tool('execute_budget_change',budget=120,idempotency_key='operation',approval_id='approval-id'),
                       final('pending_verification')])
        result=MetaBaselineAgent(client).apply(context(data,['get_campaign_metrics','propose_budget_change','execute_budget_change']))
        self.assertEqual(result.outcome,'pending_verification')
        self.assertEqual(result.metadata['model_telemetry']['orchestration_rejections'],0)

    def test_repeated_unverified_success_claim_stays_blocked(self):
        data=Tools([proposal(),receipt()])
        client=Client([tool('propose_budget_change',budget=120,idempotency_key='operation'),
                       tool('execute_budget_change',budget=120,idempotency_key='operation',approval_id='approval-id'),
                       final('executed_verified'),final('executed_verified')])
        result=MuseModelAgent(client).apply(context(data,['get_campaign_metrics','propose_budget_change','execute_budget_change']))
        self.assertEqual(result.metadata['connection_status'],'MODEL_ORCHESTRATION_BLOCKED')
        self.assertEqual(result.metadata['model_telemetry']['model_call_count'],4)
        self.assertEqual(len(data.calls),2)

    def test_orchestration_telemetry_is_json_serializable_result_metadata(self):
        from dataclasses import asdict
        result=MetaBaselineAgent(Client([final(evidence=[unknown(['absent'])]),final()])).apply(context(Tools([]),[]))
        exported=json.loads(json.dumps(asdict(result)))
        stats=exported['metadata']['model_telemetry']
        self.assertEqual(stats['orchestration_rejections'],1)
        self.assertEqual(stats['orchestration_feedback_codes'],['EVIDENCE_REFERENCE_INVALID'])
        self.assertEqual(stats['orchestration_events'],[{
            'code':'EVIDENCE_REFERENCE_INVALID','no_progress':False,
            'tool_event_count':0,'feedback_sent':True,'blocked':False}])
        self.assertTrue(stats['orchestration_finalization_after_feedback'])

if __name__=='__main__':unittest.main()
