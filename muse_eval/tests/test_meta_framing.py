"""Meta framing compatibility only; all provider HTTP calls are mocked."""
from copy import deepcopy
from dataclasses import asdict, replace
import io
import json
import unittest
from unittest.mock import Mock, patch

from muse_eval.agents.model.base import ModelConfig, ModelProviderError
from muse_eval.agents.model.meta_baseline import MetaBaselineAgent
from muse_eval.agents.model.muse_candidate import MuseModelAgent
from muse_eval.agents.model.parser import decision_schema, parse_decision, InvalidModelOutput
from muse_eval.agents.model.provider import ChatCompletionsClient, _meta_json_object
from muse_eval.schemas.result import TaskContext
from muse_eval.connectors.base import ToolResult

CONFIG=ModelConfig('Meta Model API','muse-spark-1.3','https://api.meta.ai/v1/chat/completions',family='meta_muse')
PREFIX='Investigating the CPC spike â pulling campaign data to separate facts from unknowns.'
FINAL={'decision':{'kind':'final','result':{'actions':[],'approval_state':'not_required',
       'decision_summary':'Placeholder - tool calls pending','evidence':[],'outcome':'insufficient_data'}}}
TOOL={'decision':{'kind':'tool','tool':'get_campaign_metrics','args':{'resource_id':'campaign_A'}}}

class MetaFramingTests(unittest.TestCase):
    def http_response(self,content):
        body={'model':CONFIG.model,'choices':[{'message':{'content':content}}],
              'usage':{'prompt_tokens':14,'completion_tokens':116}}
        fp=io.BytesIO(json.dumps(body).encode());fp.status=200
        return fp

    def generate(self,content,config=CONFIG):
        opener=Mock();opener.open.return_value=self.http_response(content)
        with patch('muse_eval.agents.model.provider.request.build_opener',return_value=opener):
            result=ChatCompletionsClient(config,'UNIT_TEST_ONLY').generate([],decision_schema(['get_campaign_metrics']),timeout_s=1)
        sent=json.loads(opener.open.call_args.args[0].data)
        self.assertIs(sent['response_format']['json_schema']['strict'],True)
        return result

    def test_pure_json_object_passes(self):
        content=json.dumps(FINAL)
        response=self.generate(' \t\r\n'+content+'\r\n')
        self.assertEqual(response.text,content)
        self.assertEqual(parse_decision(response,['get_campaign_metrics'])['result'].outcome,'insufficient_data')

    def test_known_real_prefix_and_json_pass_without_field_changes(self):
        content=json.dumps(FINAL,ensure_ascii=False,indent=2)
        response=self.generate(PREFIX+content)
        self.assertEqual(response.text,content)
        self.assertIsNone(response.structured_output)
        result=parse_decision(response,['get_campaign_metrics'])['result']
        self.assertEqual(result.evidence,[])
        self.assertEqual(result.actions,[])
        self.assertEqual(result.decision_summary,'Placeholder - tool calls pending')
        self.assertNotIn(PREFIX,json.dumps(asdict(response)))

    def test_prefix_and_malformed_json_fail_without_scanning_for_later_object(self):
        for content in (PREFIX+'{"decision":',PREFIX+'{broken}'+json.dumps(FINAL)):
            with self.subTest(content=content),self.assertRaises(ModelProviderError) as caught:
                self.generate(content)
            self.assertEqual(str(caught.exception),'MODEL_PROVIDER_FRAMING_INVALID')

    def test_non_whitespace_suffix_or_trailing_prose_fails(self):
        for suffix in (' trailing prose','```',' x','\x00'):
            with self.subTest(suffix=suffix),self.assertRaises(ModelProviderError):
                self.generate(PREFIX+json.dumps(FINAL)+suffix)

    def test_multiple_json_objects_fail(self):
        for prefix in ('',PREFIX):
            with self.subTest(prefix=prefix),self.assertRaises(ModelProviderError):
                self.generate(prefix+json.dumps(FINAL)+' \n '+json.dumps(TOOL))

    def test_braces_escapes_and_unicode_inside_json_strings_preserve_content(self):
        value=deepcopy(FINAL)
        value['decision']['result']['decision_summary']='Braces {nested} and } escaped quote " and Unicode Î©'
        raw=json.dumps(value,ensure_ascii=True,indent=2)
        response=self.generate(PREFIX+raw)
        self.assertEqual(response.text,raw)
        self.assertEqual(parse_decision(response,[])['result'].decision_summary,value['decision']['result']['decision_summary'])

    def test_no_object_or_root_array_or_scalar_fails(self):
        for content in ('',PREFIX,'[broken',json.dumps([FINAL]),json.dumps('a string'),
                        '42','true','null','NaN',PREFIX+json.dumps([FINAL])):
            with self.subTest(content=content),self.assertRaises(ModelProviderError):
                self.generate(content)

    def test_framing_does_not_repair_unknown_semantics_or_duplicate_keys(self):
        for content in (PREFIX+'{"decision":{"kind":"unknown"}}',
                        PREFIX+'{"decision":{},"decision":{}}'):
            response=self.generate(content)
            with self.subTest(content=content),self.assertRaises(InvalidModelOutput):
                parse_decision(response,['get_campaign_metrics'])

    def test_compatibility_is_not_applied_to_other_providers_or_paths(self):
        raw=PREFIX+json.dumps(FINAL)
        for endpoint in ('https://api.groq.com/openai/v1/chat/completions',
                         'https://api.meta.ai.example.invalid/v1/chat/completions',
                         'https://api.meta.ai/other/chat/completions'):
            with self.subTest(endpoint=endpoint):
                response=self.generate(raw,replace(CONFIG,endpoint=endpoint))
                self.assertEqual(response.text,raw)
                with self.assertRaises(InvalidModelOutput):parse_decision(response,[])

    def test_discarded_prefix_never_reaches_either_agent_history_or_result(self):
        class ReadTool:
            def call(self,name,args):
                return ToolResult(True,{'current_budget':100,'resource_id':'campaign_A'},metadata={'evidence_ref':'tool:1'})
        class RecordingClient(ChatCompletionsClient):
            def __init__(self):super().__init__(CONFIG,'UNIT_TEST_ONLY');self.histories=[]
            def generate(self,messages,schema,*,timeout_s):
                self.histories.append(deepcopy(messages))
                return super().generate(messages,schema,timeout_s=timeout_s)
        context=TaskContext('opaque','Read the campaign data.',{'resource_id':'campaign_A'},('get_campaign_metrics',),ReadTool())
        for cls in (MetaBaselineAgent,MuseModelAgent):
            with self.subTest(adapter=cls.__name__):
                opener=Mock();opener.open.side_effect=[self.http_response(PREFIX+json.dumps(TOOL)),self.http_response(PREFIX+json.dumps(FINAL))]
                client=RecordingClient()
                with patch('muse_eval.agents.model.provider.request.build_opener',return_value=opener):
                    result=cls(client).apply(context)
                self.assertEqual(result.metadata['connection_status'],'MODEL_RESPONSE_RECEIVED')
                self.assertEqual(result.metadata['model_telemetry']['model_call_count'],2)
                self.assertEqual(result.metadata['model_telemetry']['tool_call_count'],1)
                exported=json.dumps({'result':asdict(result),'histories':client.histories},ensure_ascii=False)
                self.assertNotIn(PREFIX,exported)
                self.assertNotIn('UNIT_TEST_ONLY',exported)
                self.assertEqual(json.loads(client.histories[1][-2]['content']),TOOL)

    def test_framing_errors_do_not_export_prefix_or_reasoning(self):
        with self.assertRaises(ModelProviderError) as caught:
            self.generate('PRIVATE_REASONING_CANARY '+json.dumps(FINAL)+' trailing prose')
        self.assertNotIn('PRIVATE_REASONING_CANARY',str(caught.exception))
        self.assertEqual(caught.exception.safe_diagnostics(),{'http_status':200,'error_type':None,'error_code':None})

    def test_normalizer_is_explicitly_bounded(self):
        with self.assertRaises(ValueError):_meta_json_object('x'*(1024*1024)+json.dumps(FINAL))

if __name__=='__main__':unittest.main()
