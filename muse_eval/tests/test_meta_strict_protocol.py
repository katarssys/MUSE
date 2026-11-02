"""Live wire-protocol regression tests. All HTTP responses are mocked."""
from dataclasses import asdict
import io
import json
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from muse_eval.agents.model.base import ModelConfig, ModelProviderError, ModelResponse
from muse_eval.agents.model.meta_baseline import MetaBaselineAgent
from muse_eval.agents.model.muse_candidate import MuseModelAgent
from muse_eval.agents.model.parser import decision_schema, parse_decision, InvalidModelOutput
from muse_eval.agents.model.prompts import TOOL_SPECS
from muse_eval.agents.model.provider import ChatCompletionsClient
from muse_eval.schemas.result import TaskContext

CONFIG=ModelConfig('Meta Model API','muse-spark-1.3','https://api.meta.ai/v1/chat/completions',family='meta_muse')
TOOL={'decision':{'kind':'tool','tool':'get_campaign_metrics','args':{'resource_id':'campaign_A'}}}
FINAL={'decision':{'kind':'final','result':{'outcome':'insufficient_data','evidence':[],'actions':[],
                                         'approval_state':'not_required','decision_summary':'Evidence needed.'}}}

class MetaStrictProtocolTests(unittest.TestCase):
    def assert_strict_schema(self,schema):
        self.assertEqual(schema['type'],'object')
        self.assertNotIn('oneOf',schema)
        self.assertNotIn('anyOf',schema)
        self.assertEqual(schema['required'],['decision'])
        self.assertIn('anyOf',schema['properties']['decision'])
        def visit(node,path=()):
            if isinstance(node,dict):
                self.assertNotIn('oneOf',node)
                if 'anyOf' in node:self.assertTrue(path)
                if node.get('type')=='object':
                    self.assertIs(node.get('additionalProperties'),False)
                    self.assertEqual(set(node['properties']),set(node['required']))
                for key,value in node.items():visit(value,path+(key,))
            elif isinstance(node,list):
                for i,value in enumerate(node):visit(value,path+(i,))
        visit(schema)

    def test_generated_schema_has_plain_root_nested_anyof_and_closed_required_objects(self):
        for tools in ([],['get_campaign_metrics'],list(TOOL_SPECS)):
            with self.subTest(tools=tools):self.assert_strict_schema(decision_schema(tools))

    def test_wrapped_tool_accepts_text_and_structured_response(self):
        for response in (ModelResponse(text=json.dumps(TOOL)),ModelResponse(structured_output=TOOL)):
            self.assertEqual(parse_decision(response,['get_campaign_metrics']),TOOL['decision'])

    def test_wrapped_final_accepts_text_and_structured_response(self):
        for response in (ModelResponse(text=json.dumps(FINAL)),ModelResponse(structured_output=FINAL)):
            result=parse_decision(response,['get_campaign_metrics'])
            self.assertEqual(result['kind'],'final')
            self.assertEqual(result['result'].outcome,'insufficient_data')

    def test_missing_extra_unknown_and_malformed_envelopes_fail_closed(self):
        malformed=[{},TOOL['decision'],{'decision':None},{'decision':TOOL['decision'],'extra':True},
                   {'decision':{'kind':'unknown'}},{'decision':{'kind':'tool','tool':'unknown','args':{}}},
                   {'decision':{'kind':'tool','tool':'get_campaign_metrics','args':{'resource_id':'campaign_A','extra':1}}},
                   {'decision':{'kind':'final','result':{'outcome':'invented'}}}]
        for value in malformed:
            with self.subTest(value=value),self.assertRaises(InvalidModelOutput):
                parse_decision(ModelResponse(structured_output=value),['get_campaign_metrics'])
        with self.assertRaises(InvalidModelOutput):
            parse_decision(ModelResponse(text='{"decision":{},"decision":{}}'),[])

    def test_wrapped_invalid_claims_and_actions_are_not_repaired(self):
        for field,value in [('evidence',[{'type':'metric','subject':'get_sales','metric':'revenue','value':1,
                                          'certainty':'invented','source_refs':[]}]),
                            ('actions',[{'action_type':'execute_budget_change','resource':'campaign_A',
                                         'requested_parameters':{'budget':True},'status':'EXECUTED','receipt_ref':None}])]:
            payload=json.loads(json.dumps(FINAL));payload['decision']['result'][field]=value
            with self.subTest(field=field),self.assertRaises(InvalidModelOutput):
                parse_decision(ModelResponse(structured_output=payload),[])

    def test_actual_client_sends_compatible_schema_and_keeps_strict_true(self):
        body={'model':CONFIG.model,'choices':[{'message':{'content':json.dumps(TOOL)}}],
              'usage':{'prompt_tokens':14,'completion_tokens':116}}
        fp=io.BytesIO(json.dumps(body).encode());fp.status=200
        opener=Mock();opener.open.return_value=fp
        with patch('muse_eval.agents.model.provider.request.build_opener',return_value=opener):
            response=ChatCompletionsClient(CONFIG,'UNIT_TEST_ONLY').generate([],decision_schema(list(TOOL_SPECS)),timeout_s=1)
        payload=json.loads(opener.open.call_args.args[0].data)
        response_format=payload['response_format']
        self.assertEqual(response_format['type'],'json_schema')
        self.assertIs(response_format['json_schema']['strict'],True)
        self.assert_strict_schema(response_format['json_schema']['schema'])
        self.assertEqual(parse_decision(response,list(TOOL_SPECS))['kind'],'tool')
        self.assertEqual(response.provider_metadata['returned_model'],CONFIG.model)
        self.assertEqual(response.provider_metadata['http_status'],200)

    def mocked_http_error(self,body,status=400):
        opener=Mock()
        opener.open.side_effect=HTTPError(CONFIG.endpoint,status,'DO_NOT_EXPORT',
                                          {'Authorization':'Bearer UNIT_TEST_ONLY'},io.BytesIO(body))
        return opener

    def test_http_schema_error_retains_only_allowlisted_diagnostics(self):
        body=json.dumps({'error':{'type':'invalid_request_error','code':'invalid_json_schema',
                                 'message':'SECRET_CANARY PROMPT_CANARY PRIVATE_REASONING'}}).encode()
        opener=self.mocked_http_error(body)
        with patch('muse_eval.agents.model.provider.request.build_opener',return_value=opener):
            with self.assertRaises(ModelProviderError) as captured:
                ChatCompletionsClient(CONFIG,'UNIT_TEST_ONLY').generate([],{},timeout_s=1)
        error=captured.exception
        self.assertEqual(error.safe_diagnostics(),{'http_status':400,'error_type':'invalid_request_error','error_code':'invalid_json_schema'})
        exported=json.dumps(error.safe_diagnostics())+str(error)
        for canary in ('SECRET_CANARY','PROMPT_CANARY','PRIVATE_REASONING','UNIT_TEST_ONLY','Authorization','DO_NOT_EXPORT'):
            self.assertNotIn(canary,exported)

    def test_unknown_or_non_json_provider_details_are_not_exported(self):
        for body in (b'non-JSON SECRET_CANARY',
                     json.dumps({'error':{'type':'SECRET_CANARY','code':'SECRET_CANARY','message':'PRIVATE_REASONING'}}).encode(),
                     b'x'*65537):
            with self.subTest(size=len(body)):
                opener=self.mocked_http_error(body,401)
                with patch('muse_eval.agents.model.provider.request.build_opener',return_value=opener):
                    with self.assertRaises(ModelProviderError) as captured:
                        ChatCompletionsClient(CONFIG,'UNIT_TEST_ONLY').generate([],{},timeout_s=1)
                self.assertEqual(captured.exception.safe_diagnostics(),{'http_status':401,'error_type':None,'error_code':None})

    def test_safe_http_diagnostics_reach_both_adapter_results(self):
        class NoTools:
            def call(self,*args):raise AssertionError('No tool call expected on provider failure')
        context=TaskContext('opaque','Read campaign metrics.',{'resource_id':'campaign_A'},('get_campaign_metrics',),NoTools())
        for cls in (MetaBaselineAgent,MuseModelAgent):
            body=json.dumps({'error':{'type':'invalid_request_error','code':'invalid_json_schema','message':'SECRET_CANARY'}}).encode()
            with self.subTest(adapter=cls.__name__):
                opener=self.mocked_http_error(body)
                with patch('muse_eval.agents.model.provider.request.build_opener',return_value=opener):
                    result=cls(ChatCompletionsClient(CONFIG,'UNIT_TEST_ONLY')).apply(context)
                self.assertEqual(result.metadata['connection_status'],'MODEL_PROVIDER_ERROR')
                stats=result.metadata['model_telemetry']
                self.assertEqual(stats['model_call_count'],1)
                self.assertEqual(stats['provider_error']['http_status'],400)
                self.assertEqual(stats['provider_error']['error_code'],'invalid_json_schema')
                self.assertNotIn('SECRET_CANARY',json.dumps(asdict(result)))
                self.assertNotIn('UNIT_TEST_ONLY',json.dumps(asdict(result)))

if __name__=='__main__':unittest.main()
"""Live wire-protocol regression tests. All HTTP responses are mocked."""
from dataclasses import asdict
import io
import json
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from muse_eval.agents.model.base import ModelConfig, ModelProviderError, ModelResponse
from muse_eval.agents.model.meta_baseline import MetaBaselineAgent
from muse_eval.agents.model.muse_candidate import MuseModelAgent
from muse_eval.agents.model.parser import decision_schema, parse_decision, InvalidModelOutput
from muse_eval.agents.model.prompts import TOOL_SPECS
from muse_eval.agents.model.provider import ChatCompletionsClient
from muse_eval.schemas.result import TaskContext

CONFIG=ModelConfig('Meta Model API','muse-spark-1.3','https://api.meta.ai/v1/chat/completions',family='meta_muse')
TOOL={'decision':{'kind':'tool','tool':'get_campaign_metrics','args':{'resource_id':'campaign_A'}}}
FINAL={'decision':{'kind':'final','result':{'outcome':'insufficient_data','evidence':[],'actions':[],
                                         'approval_state':'not_required','decision_summary':'Evidence needed.'}}}

class MetaStrictProtocolTests(unittest.TestCase):
    def assert_strict_schema(self,schema):
        self.assertEqual(schema['type'],'object')
        self.assertNotIn('oneOf',schema)
        self.assertNotIn('anyOf',schema)
        self.assertEqual(schema['required'],['decision'])
        self.assertIn('anyOf',schema['properties']['decision'])
        def visit(node,path=()):
            if isinstance(node,dict):
                self.assertNotIn('oneOf',node)
                if 'anyOf' in node:self.assertTrue(path)
                if node.get('type')=='object':
                    self.assertIs(node.get('additionalProperties'),False)
                    self.assertEqual(set(node['properties']),set(node['required']))
                for key,value in node.items():visit(value,path+(key,))
            elif isinstance(node,list):
                for i,value in enumerate(node):visit(value,path+(i,))
        visit(schema)

    def test_generated_schema_has_plain_root_nested_anyof_and_closed_required_objects(self):
        for tools in ([],['get_campaign_metrics'],list(TOOL_SPECS)):
            with self.subTest(tools=tools):self.assert_strict_schema(decision_schema(tools))

    def test_wrapped_tool_accepts_text_and_structured_response(self):
        for response in (ModelResponse(text=json.dumps(TOOL)),ModelResponse(structured_output=TOOL)):
            self.assertEqual(parse_decision(response,['get_campaign_metrics']),TOOL['decision'])

    def test_wrapped_final_accepts_text_and_structured_response(self):
        for response in (ModelResponse(text=json.dumps(FINAL)),ModelResponse(structured_output=FINAL)):
            result=parse_decision(response,['get_campaign_metrics'])
            self.assertEqual(result['kind'],'final')
            self.assertEqual(result['result'].outcome,'insufficient_data')

    def test_missing_extra_unknown_and_malformed_envelopes_fail_closed(self):
        malformed=[{},TOOL['decision'],{'decision':None},{'decision':TOOL['decision'],'extra':True},
                   {'decision':{'kind':'unknown'}},{'decision':{'kind':'tool','tool':'unknown','args':{}}},
                   {'decision':{'kind':'tool','tool':'get_campaign_metrics','args':{'resource_id':'campaign_A','extra':1}}},
                   {'decision':{'kind':'final','result':{'outcome':'invented'}}}]
        for value in malformed:
            with self.subTest(value=value),self.assertRaises(InvalidModelOutput):
                parse_decision(ModelResponse(structured_output=value),['get_campaign_metrics'])
        with self.assertRaises(InvalidModelOutput):
            parse_decision(ModelResponse(text='{"decision":{},"decision":{}}'),[])

    def test_wrapped_invalid_claims_and_actions_are_not_repaired(self):
        for field,value in [('evidence',[{'type':'metric','subject':'get_sales','metric':'revenue','value':1,
                                          'certainty':'invented','source_refs':[]}]),
                            ('actions',[{'action_type':'execute_budget_change','resource':'campaign_A',
                                         'requested_parameters':{'budget':True},'status':'EXECUTED','receipt_ref':None}])]:
            payload=json.loads(json.dumps(FINAL));payload['decision']['result'][field]=value
            with self.subTest(field=field),self.assertRaises(InvalidModelOutput):
                parse_decision(ModelResponse(structured_output=payload),[])

    def test_actual_client_sends_compatible_schema_and_keeps_strict_true(self):
        body={'model':CONFIG.model,'choices':[{'message':{'content':json.dumps(TOOL)}}],
              'usage':{'prompt_tokens':14,'completion_tokens':116}}
        fp=io.BytesIO(json.dumps(body).encode());fp.status=200
        opener=Mock();opener.open.return_value=fp
        with patch('muse_eval.agents.model.provider.request.build_opener',return_value=opener):
            response=ChatCompletionsClient(CONFIG,'UNIT_TEST_ONLY').generate([],decision_schema(list(TOOL_SPECS)),timeout_s=1)
        payload=json.loads(opener.open.call_args.args[0].data)
        response_format=payload['response_format']
        self.assertEqual(response_format['type'],'json_schema')
        self.assertIs(response_format['json_schema']['strict'],True)
        self.assert_strict_schema(response_format['json_schema']['schema'])
        self.assertEqual(parse_decision(response,list(TOOL_SPECS))['kind'],'tool')
        self.assertEqual(response.provider_metadata['returned_model'],CONFIG.model)
        self.assertEqual(response.provider_metadata['http_status'],200)

    def mocked_http_error(self,body,status=400):
        opener=Mock()
        opener.open.side_effect=HTTPError(CONFIG.endpoint,status,'DO_NOT_EXPORT',
                                          {'Authorization':'Bearer UNIT_TEST_ONLY'},io.BytesIO(body))
        return opener

    def test_http_schema_error_retains_only_allowlisted_diagnostics(self):
        body=json.dumps({'error':{'type':'invalid_request_error','code':'invalid_json_schema',
                                 'message':'SECRET_CANARY PROMPT_CANARY PRIVATE_REASONING'}}).encode()
        opener=self.mocked_http_error(body)
        with patch('muse_eval.agents.model.provider.request.build_opener',return_value=opener):
            with self.assertRaises(ModelProviderError) as captured:
                ChatCompletionsClient(CONFIG,'UNIT_TEST_ONLY').generate([],{},timeout_s=1)
        error=captured.exception
        self.assertEqual(error.safe_diagnostics(),{'http_status':400,'error_type':'invalid_request_error','error_code':'invalid_json_schema'})
        exported=json.dumps(error.safe_diagnostics())+str(error)
        for canary in ('SECRET_CANARY','PROMPT_CANARY','PRIVATE_REASONING','UNIT_TEST_ONLY','Authorization','DO_NOT_EXPORT'):
            self.assertNotIn(canary,exported)

    def test_unknown_or_non_json_provider_details_are_not_exported(self):
        for body in (b'non-JSON SECRET_CANARY',
                     json.dumps({'error':{'type':'SECRET_CANARY','code':'SECRET_CANARY','message':'PRIVATE_REASONING'}}).encode(),
                     b'x'*65537):
            with self.subTest(size=len(body)):
                opener=self.mocked_http_error(body,401)
                with patch('muse_eval.agents.model.provider.request.build_opener',return_value=opener):
                    with self.assertRaises(ModelProviderError) as captured:
                        ChatCompletionsClient(CONFIG,'UNIT_TEST_ONLY').generate([],{},timeout_s=1)
                self.assertEqual(captured.exception.safe_diagnostics(),{'http_status':401,'error_type':None,'error_code':None})

    def test_safe_http_diagnostics_reach_both_adapter_results(self):
        class NoTools:
            def call(self,*args):raise AssertionError('No tool call expected on provider failure')
        context=TaskContext('opaque','Read campaign metrics.',{'resource_id':'campaign_A'},('get_campaign_metrics',),NoTools())
        for cls in (MetaBaselineAgent,MuseModelAgent):
            body=json.dumps({'error':{'type':'invalid_request_error','code':'invalid_json_schema','message':'SECRET_CANARY'}}).encode()
            with self.subTest(adapter=cls.__name__):
                opener=self.mocked_http_error(body)
                with patch('muse_eval.agents.model.provider.request.build_opener',return_value=opener):
                    result=cls(ChatCompletionsClient(CONFIG,'UNIT_TEST_ONLY')).apply(context)
                self.assertEqual(result.metadata['connection_status'],'MODEL_PROVIDER_ERROR')
                stats=result.metadata['model_telemetry']
                self.assertEqual(stats['model_call_count'],1)
                self.assertEqual(stats['provider_error']['http_status'],400)
                self.assertEqual(stats['provider_error']['error_code'],'invalid_json_schema')
                self.assertNotIn('SECRET_CANARY',json.dumps(asdict(result)))
                self.assertNotIn('UNIT_TEST_ONLY',json.dumps(asdict(result)))

if __name__=='__main__':unittest.main()
