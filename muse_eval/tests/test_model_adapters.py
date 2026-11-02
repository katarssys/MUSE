"""Protocol tests only: scripted responses / mocked HTTP, never Meta inference."""
from dataclasses import asdict, replace
from copy import deepcopy
import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from muse_eval.agents.model.base import ModelConfig, ModelResponse, ModelProviderError, ModelNotConnected
from muse_eval.agents.model.meta_baseline import MetaBaselineAgent
from muse_eval.agents.model.muse_candidate import MuseModelAgent
from muse_eval.agents.model.parser import parse_decision, InvalidModelOutput, decision_schema
from muse_eval.agents.model.provider import ChatCompletionsClient, _NoRedirect
from muse_eval.agents.model.run_benchmark import run_benchmark, selected_scenarios, frozen_fingerprint
from muse_eval.schemas.result import TaskContext, validate_result
from muse_eval.harness.worker import execute_agent
from muse_eval.harness.telemetry import Telemetry
from muse_eval.connectors.mock import MockConnector
from muse_eval.schemas.scenario import Scenario
from muse_eval.harness.run_task import PACKAGE

TEST_CONFIG=ModelConfig('TEST_DOUBLE','test-only-not-meta','https://example.invalid/chat/completions')

def final_decision(outcome='insufficient_data'):
    return {'kind':'final','result':{'outcome':outcome,'evidence':[], 'actions':[],
            'approval_state':'not_required','decision_summary':'Concise public summary.'}}

def tool_decision(tool='get_sales',**args):
    return {'kind':'tool','tool':tool,'args':{'resource_id':'campaign_A',**args}}

class ScriptedClient:
    """Not a model; tracks inputs and returns predefined protocol test messages."""
    def __init__(self,responses,config=TEST_CONFIG):
        self.config=config;self.responses=iter(responses);self.inputs=[]
    def generate(self,messages,schema,*,timeout_s):
        self.inputs.append((deepcopy(messages),deepcopy(schema),timeout_s))
        response=next(self.responses)
        if isinstance(response,Exception):raise response
        return response

class SpawnProtocolProbe(MetaBaselineAgent):
    def __init__(self):
        super().__init__(ScriptedClient([ModelResponse(structured_output=tool_decision()),
                                        ModelResponse(structured_output=final_decision())]))

class ModelAdapterTests(unittest.TestCase):
    def test_configuration_accepts_explicit_meta_families(self):
        self.assertEqual(replace(TEST_CONFIG,family='meta_llama').family,'meta_llama')
        config=ModelConfig(provider='Meta Model API',model='muse-spark-1.3',
                           endpoint='https://api.meta.ai/v1/chat/completions',family='meta_muse')
        self.assertEqual(config.family,'meta_muse')
        self.assertEqual(config.model,'muse-spark-1.3')
        self.assertEqual(config.provider,'Meta Model API')
        for family in ('meta_llama','meta_muse'):
            with self.subTest(family=family),self.assertRaises(ValueError):
                replace(TEST_CONFIG,provider='',family=family)

    def test_configuration_rejects_unknown_meta_families(self):
        for family in ('', 'unknown', 'meta', 'llama', 'meta_spark', 'META_MUSE', 'qwen', None, 1, []):
            with self.subTest(family=family),self.assertRaises(ValueError):
                replace(TEST_CONFIG,family=family)

    def context(self,number=11):
        s=Scenario.load(next((PACKAGE/'task/scenarios').glob(f'{number:02d}_*.json')))
        c=MockConnector(s,Telemetry())
        return TaskContext(s.id,s.user_request,s.initial_state,tuple(s.available_tools),c),c,s

    def test_missing_provider_is_not_connected_not_simulated(self):
        with patch.dict(os.environ,{},clear=True):
            ctx,c,_=self.context()
            result=MetaBaselineAgent().apply(ctx)
            self.assertEqual(result.metadata['connection_status'],'MODEL_NOT_CONNECTED')
            self.assertEqual(result.metadata['model_telemetry']['model_call_count'],0)
            self.assertIsNone(result.metadata['model_telemetry']['estimated_cost'])
            self.assertEqual(c.events,[])

    def test_loop_observation_continuation_and_usage(self):
        ctx,c,_=self.context(1)
        client=ScriptedClient([
            ModelResponse(structured_output=tool_decision(),usage={'input_tokens':10,'output_tokens':4},estimated_cost=.001),
            ModelResponse(text=json.dumps(final_decision()),usage={'input_tokens':20,'output_tokens':5},estimated_cost=.002)])
        result=MetaBaselineAgent(client).apply(ctx)
        self.assertEqual(result.outcome,'insufficient_data')
        validate_result(asdict(result))
        self.assertIn('tool_observation',client.inputs[1][0][-1]['content'])
        telemetry=result.metadata['model_telemetry']
        self.assertEqual(telemetry['model_call_count'],2)
        self.assertEqual(telemetry['tool_call_count'],1)
        self.assertEqual(telemetry['input_tokens'],30)
        self.assertEqual(telemetry['output_tokens'],9)
        self.assertAlmostEqual(telemetry['estimated_cost'],.003)
        self.assertGreaterEqual(telemetry['model_latency_ms'],0)

    def test_unknown_usage_and_cost_stay_null(self):
        ctx,_,_=self.context()
        client=ScriptedClient([ModelResponse(structured_output=final_decision())])
        telemetry=MuseModelAgent(client).apply(ctx).metadata['model_telemetry']
        for key in ('input_tokens','output_tokens','estimated_cost'):self.assertIsNone(telemetry[key])

    def test_partial_usage_does_not_become_false_total(self):
        ctx,_,_=self.context(1)
        client=ScriptedClient([ModelResponse(structured_output=tool_decision(),usage={'input_tokens':4}),
                               ModelResponse(structured_output=final_decision(),usage={'input_tokens':3,'output_tokens':8})])
        usage=MetaBaselineAgent(client).apply(ctx).metadata['model_telemetry']
        self.assertEqual(usage['input_tokens'],7)
        self.assertIsNone(usage['output_tokens'])

    def test_same_config_tools_schema_and_user_context(self):
        ctx,_,_=self.context(12)
        ctx.initial_state['fixture_data']={'CANARY':True}
        ctx.initial_state['expected_outcome']='PRIVATE_EXPECTATION'
        clients=[ScriptedClient([ModelResponse(structured_output=final_decision())]) for _ in range(2)]
        MetaBaselineAgent(clients[0]).apply(ctx);MuseModelAgent(clients[1]).apply(ctx)
        left,right=[c.inputs[0] for c in clients]
        self.assertEqual(left[1],right[1])
        self.assertEqual(left[0][1],right[0][1])
        self.assertNotEqual(left[0][0],right[0][0])
        public=json.dumps(left[0][1])
        for hidden in ('PRIVATE_EXPECTATION','CANARY','fixture_data','success_conditions','required_evidence','12_gross_net_revenue'):
            self.assertNotIn(hidden,public)
        for client in clients:self.assertEqual(client.config,TEST_CONFIG)

    def test_model_call_and_tool_limits_are_enforced(self):
        ctx,c,_=self.context(1)
        client=ScriptedClient([ModelResponse(structured_output=tool_decision())],replace(TEST_CONFIG,max_model_calls=1))
        result=MetaBaselineAgent(client).apply(ctx)
        self.assertEqual(result.metadata['connection_status'],'MODEL_CALL_LIMIT')
        ctx,c,_=self.context(1)
        client=ScriptedClient([ModelResponse(structured_output=tool_decision()) for _ in range(2)],replace(TEST_CONFIG,max_tool_calls=1))
        result=MetaBaselineAgent(client).apply(ctx)
        self.assertEqual(result.metadata['connection_status'],'MODEL_TOOL_LIMIT')
        self.assertEqual(len(c.events),1)

    def test_context_limit_fails_without_truncating_evidence(self):
        ctx,c,_=self.context()
        client=ScriptedClient([],replace(TEST_CONFIG,max_context_chars=10))
        result=MuseModelAgent(client).apply(ctx)
        self.assertEqual(result.metadata['connection_status'],'MODEL_CONTEXT_LIMIT')
        self.assertEqual(client.inputs,[])

    def test_provider_error_does_not_leak_response_or_key(self):
        ctx,_,_=self.context()
        client=ScriptedClient([ModelProviderError('SECRET_CANARY')])
        result=MetaBaselineAgent(client).apply(ctx)
        self.assertEqual(result.metadata['connection_status'],'MODEL_PROVIDER_ERROR')
        self.assertNotIn('SECRET_CANARY',json.dumps(asdict(result)))
        self.assertIsNone(result.metadata['model_telemetry']['input_tokens'])

    def test_invalid_model_output_is_not_repaired(self):
        ctx,c,_=self.context()
        result=MetaBaselineAgent(ScriptedClient([ModelResponse(text='not JSON')])).apply(ctx)
        self.assertEqual(result.metadata['connection_status'],'MODEL_OUTPUT_INVALID')
        self.assertEqual(c.events,[])

    def test_parser_rejects_forbidden_tool_duplicate_keys_and_nonfinite(self):
        for raw in ['{"kind":"final","kind":"tool"}', '{"x":NaN}', '[]']:
            with self.subTest(raw=raw),self.assertRaises(InvalidModelOutput):
                parse_decision(ModelResponse(text=raw),['get_sales'])
        with self.assertRaises(InvalidModelOutput):
            parse_decision(ModelResponse(structured_output=tool_decision('execute_budget_change',budget=120)),['get_sales'])
        with self.assertRaises(InvalidModelOutput):
            parse_decision(ModelResponse(structured_output=tool_decision('propose_budget_change',budget=True,idempotency_key='a')),['propose_budget_change'])

    def test_scoped_approval_denial_is_not_overridden(self):
        ctx,c,_=self.context(13)
        client=ScriptedClient([ModelResponse(structured_output=tool_decision('propose_budget_change',budget=150,idempotency_key='a')),
                               ModelResponse(structured_output=final_decision('awaiting_approval'))])
        result=MuseModelAgent(client).apply(ctx)
        self.assertEqual(c.budget,100)
        observation=json.loads(client.inputs[1][0][-1]['content'])['tool_observation']
        self.assertEqual(observation['data']['status'],'approval_required')
        self.assertEqual(result.outcome,'awaiting_approval')

    def test_workflow_and_receipt_aliases_do_not_leak_scenario_names(self):
        ctx,c,_=self.context(10)
        class DynamicTestClient:
            config=TEST_CONFIG
            def __init__(self):self.messages=[];self.step=0
            def generate(self,messages,schema,*,timeout_s):
                self.messages=deepcopy(messages);self.step+=1
                if self.step==1:
                    data=tool_decision('execute_budget_change',budget=120,idempotency_key='opaque',approval_id='approval-120')
                else:
                    receipt=json.loads(messages[-1]['content'])['tool_observation']['data']
                    self_ref=receipt['receipt_id']
                    data=final_decision('executed_unverified')
                    data['result']['actions']=[{'action_type':'execute_budget_change','resource':'campaign_A',
                        'requested_parameters':{'budget':120},'status':'EXECUTED','receipt_ref':self_ref}]
                return ModelResponse(structured_output=data)
        client=DynamicTestClient();result=MetaBaselineAgent(client).apply(ctx)
        self.assertNotIn('10_verified_execution',json.dumps(client.messages))
        self.assertEqual(result.actions[0]['receipt_ref'],c.events[0]['tool_result']['data']['receipt_id'])

    def test_scripted_write_readback_loop_passes_frozen_checks(self):
        # End-to-end protocol test, explicitly not a model benchmark.
        from muse_eval.harness.check_rules import check_rules
        ctx,c,s=self.context(10)
        class WriteProtocolClient:
            config=TEST_CONFIG
            def __init__(self):self.step=0;self.claims=[];self.receipt=None;self.approval=None
            def generate(self,messages,schema,*,timeout_s):
                if self.step:
                    obs=json.loads(messages[-1]['content'])['tool_observation']
                    name=json.loads(messages[-2]['content'])['tool']
                    if name.startswith('get_'):
                        for metric,value in obs['data'].items():
                            if type(value) in (str,int,float,bool):
                                self.claims.append({'type':'metric','subject':name,'metric':metric,'value':value,
                                    'source_refs':[obs['metadata']['evidence_ref']],'certainty':'FACT'})
                    if name=='propose_budget_change':self.approval=obs['data']['approval_id']
                    if name=='execute_budget_change':self.receipt=obs['data']['receipt_id']
                choices=[tool_decision('get_campaign_metrics'),tool_decision('get_sales'),
                    tool_decision('propose_budget_change',budget=120,idempotency_key='public-operation'),
                    tool_decision('execute_budget_change',budget=120,idempotency_key='public-operation',approval_id=self.approval),
                    tool_decision('get_campaign_metrics')]
                if self.step<len(choices):data=choices[self.step]
                else:
                    data=final_decision('executed_verified');data['result'].update(evidence=self.claims,approval_state='approved',
                        actions=[{'action_type':'execute_budget_change','resource':'campaign_A','requested_parameters':{'budget':120},
                                  'status':'VERIFIED','receipt_ref':self.receipt}])
                self.step+=1
                return ModelResponse(structured_output=data)
        for cls in (MetaBaselineAgent,MuseModelAgent):
            ctx,c,s=self.context(10)
            result=cls(WriteProtocolClient()).apply(ctx)
            self.assertTrue(all(check_rules(s,result,c.events)['checks'].values()))
            self.assertEqual(result.metadata['model_telemetry']['model_call_count'],6)
            self.assertEqual(result.metadata['model_telemetry']['tool_call_count'],5)
            self.assertEqual(c.budget,120)

    def test_loop_deadline_fails_after_slow_response(self):
        import time
        class SlowTestClient:
            config=replace(TEST_CONFIG,workflow_timeout_ms=1)
            def generate(self,*args,**kwargs):
                time.sleep(.01)
                return ModelResponse(structured_output=final_decision())
        ctx,_,_=self.context()
        result=MetaBaselineAgent(SlowTestClient()).apply(ctx)
        self.assertEqual(result.metadata['connection_status'],'MODEL_TIMEOUT')

    def test_spawned_adapter_uses_frozen_worker_rpc(self):
        _,c,s=self.context(1)
        result,completed,_=execute_agent(SpawnProtocolProbe(),s,c)
        self.assertTrue(completed)
        self.assertEqual(len(c.events),1)
        self.assertEqual(result.metadata['model_telemetry']['model_call_count'],2)

    def test_mocked_http_transport_and_nullable_usage(self):
        # Tests transport shape only, not provider availability or Meta inference.
        body={'model':TEST_CONFIG.model,'choices':[{'message':{'content':json.dumps(final_decision())}}],
              'usage':{'prompt_tokens':12,'completion_tokens':7}}
        opener=unittest.mock.Mock()
        opener.open.return_value=io.BytesIO(json.dumps(body).encode())
        with patch('muse_eval.agents.model.provider.request.build_opener',return_value=opener):
            response=ChatCompletionsClient(TEST_CONFIG,'TEST_KEY').generate([{'role':'user','content':'hello'}],{},timeout_s=2)
        self.assertEqual(response.usage,{'input_tokens':12,'output_tokens':7})
        req=opener.open.call_args.args[0]
        self.assertEqual(req.full_url,TEST_CONFIG.endpoint)
        self.assertEqual(json.loads(req.data)['model'],TEST_CONFIG.model)
        self.assertEqual(opener.open.call_args.kwargs['timeout'],2)
        self.assertIsNone(response.estimated_cost)

    def test_mocked_http_model_mismatch_and_redirect_fail_closed(self):
        body={'model':'different-model','choices':[{'message':{'content':'{}'}}]}
        opener=unittest.mock.Mock();opener.open.return_value=io.BytesIO(json.dumps(body).encode())
        with patch('muse_eval.agents.model.provider.request.build_opener',return_value=opener),self.assertRaises(ModelProviderError):
            ChatCompletionsClient(TEST_CONFIG,'TEST_KEY').generate([],{},timeout_s=1)
        with self.assertRaises(ModelProviderError):
            _NoRedirect().redirect_request(None,None,302,'',{},'https://other.invalid')

    def test_configuration_rejects_credentials_in_endpoint_and_missing_auth(self):
        for endpoint in ('http://example.invalid','https://user:pass@example.invalid','https://example.invalid?key=secret'):
            with self.subTest(endpoint=endpoint),self.assertRaises(ValueError):
                replace(TEST_CONFIG,endpoint=endpoint)
        with patch.dict(os.environ,{},clear=True),self.assertRaises(ModelNotConnected):ModelConfig.from_environment()

    def test_five_neutral_cases_preserve_fixtures_and_evaluator(self):
        before=frozen_fingerprint();cases=selected_scenarios()
        self.assertEqual(len(cases),5)
        for case in cases:
            original=Scenario.load(PACKAGE/'task/scenarios'/f'{case.id}.json')
            self.assertEqual(case.fixture_data,original.fixture_data)
            self.assertEqual(case.success_conditions,original.success_conditions)
            self.assertNotEqual(case.user_request,original.user_request)
        self.assertEqual(before,frozen_fingerprint())

    def test_unconnected_benchmark_reports_not_run(self):
        with patch.dict(os.environ,{},clear=True),TemporaryDirectory() as d:
            output,code=run_benchmark(d)
            manifest=json.loads((output/'manifest.json').read_text())
            summary=json.loads((output/'summary.json').read_text())
            self.assertEqual(code,2)
            self.assertEqual(manifest['status'],'MODEL_NOT_CONNECTED')
            self.assertFalse(manifest['actually_connected'])
            self.assertEqual(manifest['selected_scenario_count'],5)
            self.assertEqual(summary['scenario_count'],0)
            self.assertIsNone(summary['scores'])
            self.assertFalse((output/'baseline.json').exists())

if __name__=='__main__':unittest.main()
