"""Safe provider classifications; every transport is mocked, never live."""
from dataclasses import asdict
import io
import json
import socket
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from muse_eval.agents.model.base import ModelConfig, ModelProviderError
from muse_eval.agents.model.provider import ChatCompletionsClient
from muse_eval.agents.model.meta_baseline import MetaBaselineAgent
from muse_eval.agents.model.muse_candidate import MuseModelAgent
from muse_eval.schemas.result import TaskContext

CONFIG=ModelConfig('TEST_DOUBLE','test-model','https://example.invalid/chat/completions')
SECRET='SECRET_EXCEPTION_PROMPT_REASONING_CANARY https://private.invalid Authorization Bearer KEY_CANARY'

class ProviderDiagnosticsTests(unittest.TestCase):
    def capture(self, *, exception=None, body=None, read_exception=None):
        opener=Mock()
        if exception is not None:
            opener.open.side_effect=exception
        else:
            response=io.BytesIO(body);response.status=200
            if read_exception is not None:
                response=Mock()
                response.__enter__=Mock(return_value=response)
                response.__exit__=Mock(return_value=False)
                response.read.side_effect=read_exception
            opener.open.return_value=response
        with patch('muse_eval.agents.model.provider.request.build_opener',return_value=opener):
            with self.assertRaises(ModelProviderError) as caught:
                ChatCompletionsClient(CONFIG,'KEY_CANARY').generate(
                    [{'role':'user','content':SECRET}],{},timeout_s=15.0)
        self.assertEqual(opener.open.call_count,1)
        self.assertEqual(opener.open.call_args.kwargs['timeout'],15.0)
        exported=json.dumps(caught.exception.safe_diagnostics())+str(caught.exception)
        for forbidden in ('CANARY','private.invalid','Authorization','Bearer','Traceback'):
            self.assertNotIn(forbidden,exported)
        self.assertIsNone(caught.exception.__cause__)
        self.assertTrue(caught.exception.__suppress_context__)
        return caught.exception.safe_diagnostics()

    def test_direct_timeout_including_socket_alias(self):
        for exc in (TimeoutError(SECRET),socket.timeout(SECRET)):
            with self.subTest(kind=type(exc).__name__):
                self.assertEqual(self.capture(exception=exc)['category'],'timeout')

    def test_url_error_wrapping_timeout(self):
        self.assertEqual(self.capture(exception=URLError(socket.timeout(SECRET)))['category'],'timeout')

    def test_url_error_with_non_timeout_reason_is_not_inferred_from_message(self):
        for reason in (SECRET+' timed out',ConnectionRefusedError(SECRET)):
            self.assertEqual(self.capture(exception=URLError(reason))['category'],'url_error')

    def test_generic_connection_errors(self):
        for exc in (ConnectionResetError(SECRET),ConnectionRefusedError(SECRET),OSError(SECRET)):
            self.assertEqual(self.capture(exception=exc)['category'],'connection_error')

    def test_timeout_while_reading_response(self):
        self.assertEqual(self.capture(body=b'',read_exception=socket.timeout(SECRET))['category'],'timeout')

    def test_http_error_preserves_sanitized_details(self):
        body=json.dumps({'error':{'type':'rate_limit_error','code':'rate_limit_exceeded','message':SECRET}}).encode()
        exc=HTTPError(CONFIG.endpoint,429,SECRET,{'Authorization':SECRET},io.BytesIO(body))
        self.assertEqual(self.capture(exception=exc),{
            'category':'http_error','http_status':429,
            'error_type':'rate_limit_error','error_code':'rate_limit_exceeded'})

    def test_malformed_json_and_invalid_encoding(self):
        for body in (SECRET.encode(),b'{',b'\xff',b'{"x":NaN}'):
            self.assertEqual(self.capture(body=body)['category'],'response_json_invalid')

    def test_response_shape_failures(self):
        for value in ({},[],None,{'choices':[]},{'choices':None},
                      {'choices':[{}]},{'choices':[{'message':{'content':None}}]}):
            with self.subTest(value=value):
                self.assertEqual(self.capture(body=json.dumps(value).encode())['category'],'response_shape_invalid')

    def test_category_is_allowlisted_not_free_text(self):
        self.assertIsNone(ModelProviderError('FIXED',category=SECRET).safe_diagnostics()['category'])
        self.assertEqual(CONFIG.request_timeout_s,30.0)
        self.assertEqual(CONFIG.max_model_calls,8)
        self.assertEqual(CONFIG.max_tool_calls,8)

    def test_diagnostics_reach_both_results_without_exception_text_or_retry(self):
        for cls in (MetaBaselineAgent,MuseModelAgent):
            opener=Mock();opener.open.side_effect=URLError(TimeoutError(SECRET))
            context=TaskContext('opaque','Public request',{},(),None)
            with patch('muse_eval.agents.model.provider.request.build_opener',return_value=opener):
                result=cls(ChatCompletionsClient(CONFIG,'KEY_CANARY')).apply(context)
            telemetry=result.metadata['model_telemetry']
            self.assertEqual(result.metadata['connection_status'],'MODEL_PROVIDER_ERROR')
            self.assertEqual(telemetry['provider_error']['category'],'timeout')
            self.assertEqual(telemetry['model_call_count'],1)
            self.assertEqual(opener.open.call_count,1)
            exported=json.dumps(asdict(result))
            for forbidden in ('CANARY','private.invalid','Authorization','Bearer','Traceback'):
                self.assertNotIn(forbidden,exported)

if __name__=='__main__':unittest.main()
